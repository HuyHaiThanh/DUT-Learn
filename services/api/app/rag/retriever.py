"""Exact scoped dense retrieval and a retrieval-only evaluation CLI."""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from io import TextIOWrapper
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol, TypedDict
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import Settings, get_settings
from app.db import SessionLocal
from app.materials.models import Chunk, Material
from app.rag.embedder import Embedder, get_embedder
from app.rag.scope import scoped_chunks


@dataclass(frozen=True)
class Hit:
    chunk_id: UUID
    version_id: UUID
    material_id: UUID
    material_title: str
    kind: Literal["text", "code"]
    page_index: int
    page_index_end: int
    page_label: str | None
    char_start: int
    char_end: int
    text: str
    rank: int
    cosine: float
    bm25_score: float | None = None
    rrf_score: float | None = None
    used_in_prompt: bool = False


class Timings(TypedDict):
    embed: float
    search: float


@dataclass(frozen=True)
class RetrievalResult:
    hits: list[Hit]
    retriever: Literal["dense", "hybrid"]
    top_cosine: float | None
    timings_ms: Timings


class Retriever(Protocol):
    def retrieve(
        self,
        db: Session,
        *,
        user: User,
        class_id: UUID,
        query: str,
        k: int,
        prefer_material_id: UUID | None = None,
        prefer_page_index: int | None = None,
    ) -> RetrievalResult: ...


class DenseRetriever:
    def __init__(self, embedder: Embedder, settings: Settings | None = None) -> None:
        self.embedder = embedder
        self.settings = settings or get_settings()

    def retrieve(
        self,
        db: Session,
        *,
        user: User,
        class_id: UUID,
        query: str,
        k: int,
        prefer_material_id: UUID | None = None,
        prefer_page_index: int | None = None,
    ) -> RetrievalResult:
        query = query.strip()
        if not query:
            raise ValueError("Câu hỏi không được rỗng.")
        if k <= 0:
            raise ValueError("k phải lớn hơn 0.")
        start = perf_counter()
        vector = self.embedder.embed_query(query)
        embedded = perf_counter()
        scope = scoped_chunks(db, user=user, class_id=class_id)
        # Validate preferences through the same SQL boundary, never by fetching a material.
        preferred = (
            prefer_material_id is not None
            and db.scalar(
                scope.with_only_columns(Chunk.id).where(Material.id == prefer_material_id).limit(1)
            )
            is not None
        )
        distance = Chunk.embedding.cosine_distance(vector)
        fetched = db.execute(
            scope.add_columns(Material.id, Material.title, distance.label("distance"))
            .order_by(distance, Chunk.version_id, Chunk.ordinal)
            .limit(max(k, 20) if preferred else k)
        ).all()
        rows: list[tuple[Chunk, UUID, str, float]] = [
            (row[0], row[1], row[2], row[3]) for row in fetched
        ]
        if preferred:

            def ranking(row: tuple[Chunk, UUID, str, float]) -> tuple[float, UUID, int]:
                chunk, material_id, _, dist = row
                bonus = 0.0
                if material_id == prefer_material_id:
                    bonus += self.settings.prefer_material_bonus
                    if (
                        prefer_page_index is not None
                        and chunk.page_index <= prefer_page_index <= chunk.page_index_end
                    ):
                        bonus += self.settings.prefer_page_bonus
                return (-(1 - dist + bonus), chunk.version_id, chunk.ordinal)

            rows.sort(key=ranking)
        hits = [
            Hit(
                chunk_id=chunk.id,
                version_id=chunk.version_id,
                material_id=material_id,
                material_title=title,
                kind=chunk.kind,
                page_index=chunk.page_index,
                page_index_end=chunk.page_index_end,
                page_label=chunk.page_label,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                text=chunk.text,
                rank=rank,
                cosine=float(1 - dist),
            )
            for rank, (chunk, material_id, title, dist) in enumerate(rows[:k], 1)
        ]
        return RetrievalResult(
            hits,
            "dense",
            max((hit.cosine for hit in hits), default=None),
            {"embed": (embedded - start) * 1000, "search": (perf_counter() - embedded) * 1000},
        )


def get_retriever(settings: Settings) -> Retriever:
    if settings.retriever == "hybrid":
        raise NotImplementedError("Truy xuất hybrid sẽ được triển khai ở T16.")
    return DenseRetriever(get_embedder(settings), settings)


class Question(BaseModel):
    id: str
    question: str = Field(min_length=1)


class AnswerableQuestion(Question):
    accepted_pages: list[int] = Field(min_length=1)


class QuestionFile(BaseModel):
    e_r: list[AnswerableQuestion]
    unanswerable: list[Question] = Field(default_factory=list)


def page_metrics(result: RetrievalResult, accepted_pages: list[int]) -> tuple[float, float]:
    """Rank unique PDF pages in first-occurrence order, including cross-page chunks."""
    pages = list(
        dict.fromkeys(
            page + 1
            for hit in result.hits
            for page in range(hit.page_index, hit.page_index_end + 1)
        )
    )
    ranks = [rank for rank, page in enumerate(pages, 1) if page in accepted_pages]
    first = min(ranks, default=11)
    return float(first <= 5), 1 / first if first <= 10 else 0.0


def run_questions(
    db: Session,
    *,
    retriever: Retriever,
    user: User,
    class_id: UUID,
    questions: QuestionFile,
    k: int,
    out: Path | None = None,
    dataset_hash: str | None = None,
    report_metrics: bool = True,
) -> None:
    # Local import keeps the reusable retrieval module independent of calibration.
    from app.rag.threshold import sweep_thresholds

    traces: list[dict[str, object]] = []
    metrics: list[tuple[float, float]] = []
    pos: list[float] = []
    neg: list[float] = []
    for question in [*questions.e_r, *questions.unanswerable]:
        result = retriever.retrieve(
            db,
            user=user,
            class_id=class_id,
            query=question.question,
            k=k,
            prefer_material_id=None,
            prefer_page_index=None,
        )
        answerable = isinstance(question, AnswerableQuestion)
        print(f"id={question.id} top_cosine={result.top_cosine}")
        if isinstance(question, AnswerableQuestion):
            metrics.append(page_metrics(result, question.accepted_pages))
            for hit in result.hits:
                print(f"  {hit.rank} page={hit.page_index + 1} {hit.cosine:.4f} {hit.text[:80]}")
        if result.top_cosine is not None:
            (pos if answerable else neg).append(result.top_cosine)
        traces.append(
            {
                "id": question.id,
                "request_id": str(uuid4()),
                "retriever": result.retriever,
                "top_cosine": result.top_cosine,
                "timings_ms": result.timings_ms,
                "hits": [
                    {
                        key: value
                        for key, value in asdict(hit).items()
                        if key not in {"text", "material_title"}
                    }
                    for hit in result.hits
                ],
            }
        )
    if metrics and report_metrics:
        print(f"Hit@5={sum(m[0] for m in metrics) / len(metrics):.4f}")
        print(f"MRR@10={sum(m[1] for m in metrics) / len(metrics):.4f}")
    sweep = None
    if questions.e_r and questions.unanswerable:
        if len(pos) != len(questions.e_r) or len(neg) != len(questions.unanswerable):
            sweep = {
                "threshold": None,
                "warning": "Không hiệu chỉnh ngưỡng: có câu không có đoạn (top_cosine=null).",
            }
            print(json.dumps(sweep, ensure_ascii=False))
        else:
            sweep = asdict(sweep_thresholds(pos, neg))
            print(json.dumps(sweep, ensure_ascii=False))
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        with (out / "trace.jsonl").open("w", encoding="utf-8") as stream:
            for trace in traces:
                stream.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")
        if sweep is not None:
            (out / "thresholds.json").write_text(
                json.dumps({"dataset_sha256": dataset_hash, **sweep}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def main() -> None:
    # Windows redirected streams can default to cp1252, which cannot print Vietnamese.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Truy xuất dense trong phạm vi lớp, không gọi LLM."
    )
    parser.add_argument("--class-id", required=True, type=UUID)
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--k", type=int, default=10)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--query")
    source.add_argument("--questions", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.k <= 0:
        parser.error("--k phải lớn hơn 0.")
    dataset_hash = None
    if args.questions:
        try:
            payload = args.questions.read_bytes()
            questions = QuestionFile.model_validate_json(payload)
            dataset_hash = hashlib.sha256(payload).hexdigest()
            if any(p < 1 for q in questions.e_r for p in q.accepted_pages):
                parser.error("accepted_pages phải là trang PDF 1-based.")
        except (OSError, ValidationError) as exc:
            # Validation errors can contain input text; never echo them.
            parser.error(f"Không đọc được file câu hỏi hợp lệ ({type(exc).__name__}).")
    else:
        if not args.query.strip():
            parser.error("Câu hỏi không được rỗng.")
        questions = QuestionFile(
            e_r=[AnswerableQuestion(id="query", question=args.query, accepted_pages=[1])]
        )
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.user_email.strip().lower()))
        if user is None or not user.is_active:
            parser.error("Không có người dùng hợp lệ.")
        run_questions(
            db,
            retriever=get_retriever(get_settings()),
            user=user,
            class_id=args.class_id,
            questions=questions,
            k=args.k,
            out=args.out,
            dataset_hash=dataset_hash,
            report_metrics=args.questions is not None,
        )


if __name__ == "__main__":
    main()
