from collections import Counter
from statistics import median
from typing import Any

from app.ingest.chunk import ChunkDraft
from app.ingest.extract import Document


def quality_report(
    document: Document, chunks: list[ChunkDraft], embed_model: str, duration_ms: int
) -> dict[str, Any]:
    lengths = [len(page.text) for page in document.pages]
    blocks = Counter(chunk.code_block_id for chunk in chunks if chunk.kind == "code")
    return {
        "page_count": len(lengths),
        "empty_pages": [page.index for page in document.pages if len(page.text) < 50],
        "chars_per_page": {
            "min": min(lengths, default=0),
            "median": median(lengths) if lengths else 0,
            "max": max(lengths, default=0),
        },
        "chunk_count": {
            "text": sum(c.kind == "text" for c in chunks),
            "code": sum(c.kind == "code" for c in chunks),
        },
        "small_chunks": {
            kind: sum(c.kind == kind and c.token_count < 40 for c in chunks)
            for kind in ("text", "code")
        },
        "token_median": {
            kind: median(counts)
            if (counts := [c.token_count for c in chunks if c.kind == kind])
            else 0
            for kind in ("text", "code")
        },
        "code_blocks": {"total": len(blocks), "split": sum(n > 1 for n in blocks.values())},
        "glued_tokens_before": document.glued_tokens_before,
        "glued_tokens_after": document.glued_tokens_after,
        "reading_order_warnings": document.reading_order_warnings,
        "sample": [chunk.text[:300] for chunk in chunks[:3]],
        "embed_model": embed_model,
        "duration_ms": duration_ms,
    }
