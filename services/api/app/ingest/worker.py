import hashlib
import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from time import perf_counter
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.ingest.chunk import chunk_document
from app.ingest.extract import extract_pdf, extract_text
from app.ingest.quality import quality_report
from app.ingest.queue import wakeup
from app.materials.models import Chunk, Material, MaterialVersion
from app.materials.storage import LocalStorage, Storage
from app.rag.embedder import E5Embedder, Embedder

logger = logging.getLogger(__name__)
INTERRUPTED = "Xử lý bị gián đoạn, hãy xử lý lại."


class IngestWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        storage: Storage | None = None,
        embedder: Embedder | None = None,
        *,
        poll_seconds: float = 30,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage if storage is not None else LocalStorage()
        self.embedder = embedder if embedder is not None else E5Embedder()
        self.poll_seconds = poll_seconds
        self._stop = Event()
        self._thread: Thread | None = None

    def recover_stale(self) -> int:
        with self.session_factory() as db, db.begin():
            ids = db.scalars(
                update(MaterialVersion)
                .where(
                    MaterialVersion.status == "processing",
                    MaterialVersion.processing_started_at
                    < datetime.now(UTC) - timedelta(minutes=30),
                )
                .values(status="failed", error=INTERRUPTED)
                .returning(MaterialVersion.id)
            ).all()
            for version_id in ids:
                db.execute(delete(Chunk).where(Chunk.version_id == version_id))
        return len(ids)

    def claim(self, version_id: UUID) -> datetime | None:
        with self.session_factory() as db, db.begin():
            return db.scalar(
                update(MaterialVersion)
                .where(
                    MaterialVersion.id == version_id,
                    MaterialVersion.status.in_(["uploaded", "failed"]),
                )
                .values(status="processing", processing_started_at=func.now(), error=None)
                .returning(MaterialVersion.processing_started_at)
            )

    def process(self, version_id: UUID) -> bool:
        claimed_at = self.claim(version_id)
        if claimed_at is None:
            return False
        started = perf_counter()
        try:
            with self.session_factory() as db:
                version = db.get(MaterialVersion, version_id)
                assert version is not None
                material = db.get(Material, version.material_id)
                assert material is not None
                with self.storage.open(version.storage_key) as stream:
                    data = stream.read()
                if hashlib.sha256(data).hexdigest() != version.checksum_sha256:
                    raise ValueError("Mã kiểm tra tệp không khớp.")
                document = extract_pdf(data) if material.kind == "pdf" else extract_text(data)
            drafts = chunk_document(document, self.embedder)
            if not drafts:
                raise ValueError("Tệp không có văn bản để xử lý.")
            vectors = []
            for offset in range(0, len(drafts), 32):
                vectors.extend(
                    self.embedder.embed_passages(
                        [draft.text for draft in drafts[offset : offset + 32]]
                    )
                )
            if len(vectors) != len(drafts) or any(
                len(v) != 384
                or not all(math.isfinite(x) for x in v)
                or not math.isclose(sum(x * x for x in v), 1.0, abs_tol=1e-4)
                for v in vectors
            ):
                raise ValueError("Vector embedding không hợp lệ.")
            report = quality_report(
                document,
                drafts,
                getattr(self.embedder, "model_name", type(self.embedder).__name__),
                int((perf_counter() - started) * 1000),
            )
            with self.session_factory() as db, db.begin():
                version = db.scalar(
                    select(MaterialVersion)
                    .where(
                        MaterialVersion.id == version_id,
                        MaterialVersion.status == "processing",
                        MaterialVersion.processing_started_at == claimed_at,
                    )
                    .with_for_update()
                )
                if version is None:
                    return False  # A recovery/revocation superseded this claim.
                db.execute(delete(Chunk).where(Chunk.version_id == version_id))
                for ordinal, (draft, vector) in enumerate(zip(drafts, vectors, strict=True)):
                    db.add(
                        Chunk(
                            version_id=version_id, ordinal=ordinal, embedding=vector, **vars(draft)
                        )
                    )
                version.page_count = len(document.pages)
                version.quality_report = report
                version.status = "ready"
                version.error = None
            logger.info(
                "Ingest ready version=%s pages=%d duration_ms=%d",
                version_id,
                len(document.pages),
                report["duration_ms"],
            )
            return True
        except Exception:
            # Never persist exception strings: parsers/providers may include source content.
            with self.session_factory() as db, db.begin():
                changed = db.scalar(
                    update(MaterialVersion)
                    .where(
                        MaterialVersion.id == version_id,
                        MaterialVersion.status == "processing",
                        MaterialVersion.processing_started_at == claimed_at,
                    )
                    .values(
                        status="failed",
                        error="Không thể xử lý học liệu, hãy kiểm tra tệp và thử lại.",
                    )
                    .returning(MaterialVersion.id)
                )
                if changed is not None:
                    db.execute(delete(Chunk).where(Chunk.version_id == version_id))
            logger.warning("Ingest failed version=%s code=ingest_failed", version_id)
            return False

    def scan_once(self) -> None:
        with self.session_factory() as db:
            ids = db.scalars(
                select(MaterialVersion.id)
                .where(MaterialVersion.status == "uploaded")
                .order_by(MaterialVersion.created_at)
            ).all()
        for version_id in ids:
            if self._stop.is_set():
                break
            self.process(version_id)

    def _run(self) -> None:
        while not self._stop.is_set():
            wakeup.clear()
            try:
                self.scan_once()
            except Exception:
                logger.warning("Ingest scan failed code=ingest_scan_failed")
            wakeup.wait(self.poll_seconds)

    def start(self) -> None:
        if self._thread is not None:
            return
        self.recover_stale()
        self._stop.clear()
        self._thread = Thread(target=self._run, name="dut-ingest", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        wakeup.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
