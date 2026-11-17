import logging
from dataclasses import replace
from math import ceil

from app.config import Settings
from app.errors import APIError
from app.rag.llm import ChatMessage
from app.rag.retriever import RetrievalResult
from app.tutor.prompt import build_prompt

logger = logging.getLogger(__name__)


def estimate_tokens(messages: list[ChatMessage], settings: Settings) -> int:
    return (
        ceil(sum(len(m["content"]) for m in messages) / settings.prompt_chars_per_token)
        + settings.prompt_template_overhead
    )


def fit_prompt(
    result: RetrievalResult, question: str, mode: str, settings: Settings
) -> tuple[RetrievalResult, list[ChatMessage], int]:
    hits = sorted(result.hits, key=lambda hit: hit.rank)
    count = len(hits)
    while hits:
        messages = build_prompt(hits, question, mode)
        tokens = estimate_tokens(messages, settings)
        if (
            tokens * (1 + settings.prompt_safety_margin) + settings.llm_max_tokens
            <= settings.llm_num_ctx
        ):
            if count > len(hits):
                logger.warning("tutor prompt dropped_chunks=%s", count - len(hits))
            used = {hit.chunk_id for hit in hits}
            return (
                replace(
                    result,
                    hits=[
                        replace(h, used_in_prompt=h.chunk_id in used)
                        for h in sorted(result.hits, key=lambda h: h.rank)
                    ],
                ),
                messages,
                tokens,
            )
        if len(hits) == 1:
            break
        hits.pop()
    logger.warning("tutor prompt context_overflow dropped_chunks=%s", max(0, count - 1))
    raise APIError(
        500,
        "context_overflow",
        "Ngân sách ngữ cảnh không đủ cho một đoạn học liệu. Vui lòng báo giảng viên.",
    )
