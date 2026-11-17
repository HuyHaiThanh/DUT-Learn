import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session, sessionmaker
from test_materials import CSRF, account, upload
from test_materials import material_db as material_db

from app.ingest import queue
from app.ingest.worker import INTERRUPTED, IngestWorker
from app.main import app
from app.materials.models import Chunk, MaterialVersion
from app.materials.storage import LocalStorage
from app.rag.embedder import FakeEmbedder


@pytest.fixture(autouse=True)
def no_background_worker(monkeypatch):
    monkeypatch.setenv("DUT_INGEST_WORKER", "0")


@pytest.fixture
def job(db_client, material_db, tmp_path, test_engine):
    account(db_client, material_db)
    content = "Nội dung học liệu.\n```c\nint main() {\nreturn 0;\n}\n```".encode()
    result = upload(db_client, material_db, "lesson.md", content)
    assert result.status_code == 201, result.text
    version_id = UUID(result.json()["version"]["id"])
    worker = IngestWorker(sessionmaker(test_engine), LocalStorage(tmp_path), FakeEmbedder())
    return worker, version_id


def chunks_for(db, version_id):
    db.expire_all()
    return list(
        db.scalars(select(Chunk).where(Chunk.version_id == version_id).order_by(Chunk.ordinal))
    )


def stale_chunk(db, version_id):
    old = Chunk(
        version_id=version_id,
        ordinal=0,
        kind="text",
        page_index=0,
        page_index_end=0,
        page_label="1",
        char_start=0,
        char_end=3,
        text="old",
        token_count=4,
        embedding=FakeEmbedder().embed_query("old"),
    )
    db.add(old)
    db.commit()
    return old.id


def test_worker_ready_chunks_vectors_and_quality(job, material_db):
    worker, version_id = job
    assert worker.process(version_id)
    chunks = chunks_for(material_db, version_id)
    version = material_db.get(MaterialVersion, version_id)
    assert version.status == "ready" and version.page_count == 1 and version.error is None
    assert chunks and all(len(c.embedding) == 384 for c in chunks)
    assert set(version.quality_report) == {
        "page_count",
        "empty_pages",
        "chars_per_page",
        "chunk_count",
        "small_chunks",
        "token_median",
        "code_blocks",
        "glued_tokens_before",
        "glued_tokens_after",
        "reading_order_warnings",
        "sample",
        "embed_model",
        "duration_ms",
    }
    assert version.quality_report["chunk_count"]["code"] == 1
    assert all(len(sample) <= 300 for sample in version.quality_report["sample"])
    assert not worker.process(version_id)


def test_embedder_fails_mid_batch_zero_chunks_and_no_source_in_logs(job, material_db, caplog):
    worker, version_id = job
    version = material_db.get(MaterialVersion, version_id)
    content = ("Unique secret source words. " * 8000).encode()
    worker.storage.put(version.storage_key, content)
    version.checksum_sha256 = hashlib.sha256(content).hexdigest()
    material_db.commit()
    stale_chunk(material_db, version_id)

    class Broken(FakeEmbedder):
        calls = 0

        def embed_passages(self, texts):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("Unique secret source words.")
            return super().embed_passages(texts)

    broken = Broken()
    worker.embedder = broken
    with caplog.at_level(logging.INFO):
        assert not worker.process(version_id)
    assert broken.calls == 2
    assert chunks_for(material_db, version_id) == []
    version = material_db.get(MaterialVersion, version_id)
    assert version.status == "failed" and version.error
    assert "Unique secret" not in version.error + caplog.text


def test_insert_failure_rolls_back_and_marks_failed(job, material_db, test_engine):
    worker, version_id = job
    stale_chunk(material_db, version_id)

    def fail_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO chunks"):
            raise RuntimeError("simulated write failure")

    event.listen(test_engine, "before_cursor_execute", fail_insert)
    try:
        assert not worker.process(version_id)
    finally:
        event.remove(test_engine, "before_cursor_execute", fail_insert)
    assert chunks_for(material_db, version_id) == []
    version = material_db.get(MaterialVersion, version_id)
    assert version.status == "failed" and version.quality_report is None


@pytest.mark.parametrize("failure", ["checksum", "missing", "invalid_text", "empty"])
def test_bad_input_failed_without_chunks(job, material_db, failure):
    worker, version_id = job
    version = material_db.get(MaterialVersion, version_id)
    if failure == "checksum":
        version.checksum_sha256 = "0" * 64
    elif failure == "missing":
        version.storage_key = "materials/missing.md"
    else:
        content = b"\xff" if failure == "invalid_text" else b""
        worker.storage.put(version.storage_key, content)
        version.checksum_sha256 = hashlib.sha256(content).hexdigest()
    material_db.commit()
    assert not worker.process(version_id)
    assert chunks_for(material_db, version_id) == []
    assert material_db.get(MaterialVersion, version_id).status == "failed"


def test_failed_reprocess_replaces_old_chunks_and_queues_after_commit(
    job, material_db, db_client, monkeypatch, test_engine
):
    worker, version_id = job
    version = material_db.get(MaterialVersion, version_id)
    version.status = "failed"
    material_db.commit()
    old_id = stale_chunk(material_db, version_id)
    calls = []

    def enqueue(id):
        with Session(test_engine) as other:
            assert other.get(MaterialVersion, id).status == "uploaded"
        calls.append(id)

    monkeypatch.setattr(queue, "enqueue_ingest", enqueue)
    response = db_client.post(f"/api/material-versions/{version_id}/reprocess", headers=CSRF)
    assert response.status_code == 200 and response.json()["status"] == "uploaded"
    assert calls == [version_id]
    assert worker.process(version_id)
    chunks = chunks_for(material_db, version_id)
    assert chunks and old_id not in {c.id for c in chunks}
    assert material_db.get(MaterialVersion, version_id).status == "ready"


@pytest.mark.parametrize(
    "state", ["uploaded", "processing", "ready", "published", "superseded", "revoked"]
)
def test_reprocess_only_accepts_failed(job, material_db, db_client, monkeypatch, state):
    _, version_id = job
    version = material_db.get(MaterialVersion, version_id)
    version.status = state
    material_db.commit()
    calls = []
    monkeypatch.setattr(queue, "enqueue_ingest", calls.append)
    response = db_client.post(f"/api/material-versions/{version_id}/reprocess", headers=CSRF)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"
    material_db.expire_all()
    assert material_db.get(MaterialVersion, version_id).status == state and not calls


@pytest.mark.parametrize(
    "actor,status",
    [("gv1", 200), ("sv1", 403), ("gv2", 404), ("sv3", 404), ("admin", 404), (None, 401)],
)
def test_reprocess_permission_matrix(job, material_db, db_client, actor, status):
    _, version_id = job
    version = material_db.get(MaterialVersion, version_id)
    version.status = "failed"
    material_db.commit()
    account(db_client, material_db, actor)
    response = db_client.post(f"/api/material-versions/{version_id}/reprocess", headers=CSRF)
    assert response.status_code == status
    material_db.expire_all()
    assert material_db.get(MaterialVersion, version_id).status == (
        "uploaded" if status == 200 else "failed"
    )


def test_reprocess_requires_csrf(job, material_db, db_client):
    _, version_id = job
    version = material_db.get(MaterialVersion, version_id)
    version.status = "failed"
    material_db.commit()
    response = db_client.post(f"/api/material-versions/{version_id}/reprocess")
    assert response.status_code == 403 and response.json()["error"]["code"] == "csrf_required"
    material_db.expire_all()
    assert material_db.get(MaterialVersion, version_id).status == "failed"


def test_unknown_reprocess_is_404(job, db_client):
    assert (
        db_client.post(f"/api/material-versions/{uuid4()}/reprocess", headers=CSRF).status_code
        == 404
    )


def test_startup_recovers_stale_processing_only(job, material_db):
    worker, version_id = job
    version = material_db.get(MaterialVersion, version_id)
    version.status = "processing"
    version.processing_started_at = datetime.now(UTC) - timedelta(minutes=31)
    material_db.commit()
    stale_chunk(material_db, version_id)
    worker.start()
    worker.stop()
    assert chunks_for(material_db, version_id) == []
    version = material_db.get(MaterialVersion, version_id)
    assert version.status == "failed" and version.error == INTERRUPTED
    assert worker.recover_stale() == 0
    version.status = "processing"
    version.processing_started_at = datetime.now(UTC)
    material_db.commit()
    assert worker.recover_stale() == 0


def test_two_workers_only_one_can_claim(job, test_engine):
    worker, version_id = job
    other = IngestWorker(sessionmaker(test_engine), worker.storage, FakeEmbedder())
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda w: w.claim(version_id), [worker, other]))
    assert sum(claim is not None for claim in claims) == 1


def test_scan_processes_uploaded_not_failed(job, material_db):
    worker, version_id = job
    worker.scan_once()
    material_db.expire_all()
    version = material_db.get(MaterialVersion, version_id)
    assert version.status == "ready"
    version.status = "failed"
    material_db.commit()
    worker.scan_once()
    material_db.expire_all()
    assert material_db.get(MaterialVersion, version_id).status == "failed"


def test_queue_wakes_thread_and_periodic_scan(monkeypatch):
    worker = IngestWorker(storage=Mock(), embedder=FakeEmbedder(), poll_seconds=0.02)
    monkeypatch.setattr(worker, "recover_stale", lambda: 0)
    scanned = Event()
    calls = []

    def scan():
        calls.append(1)
        scanned.set()

    monkeypatch.setattr(worker, "scan_once", scan)
    worker.start()
    try:
        assert worker._thread.daemon
        assert scanned.wait(2)
        scanned.clear()
        assert scanned.wait(2)  # periodic polling, without enqueue
        scanned.clear()
        queue.enqueue_ingest(uuid4())
        assert scanned.wait(2)
        assert len(calls) >= 3
    finally:
        worker.stop()
    assert worker._thread is None


def test_lifespan_starts_stops_and_can_disable_worker(monkeypatch):
    from fastapi.testclient import TestClient

    instance = Mock()
    factory = Mock(return_value=instance)
    monkeypatch.setattr("app.main.IngestWorker", factory)
    monkeypatch.setenv("DUT_INGEST_WORKER", "1")
    with TestClient(app):
        instance.start.assert_called_once()
    instance.stop.assert_called_once()
    factory.reset_mock()
    monkeypatch.setenv("DUT_INGEST_WORKER", "0")
    with TestClient(app):
        pass
    factory.assert_not_called()
