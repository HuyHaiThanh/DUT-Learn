"""Tokenizer bounded text windows and line-preserving code chunks."""

import re
from dataclasses import dataclass
from typing import Literal

from app.ingest.extract import Document, Line, Page
from app.rag.embedder import Embedder


@dataclass
class ChunkDraft:
    kind: Literal["text", "code"]
    page_index: int
    page_index_end: int
    page_label: str
    char_start: int
    char_end: int
    text: str
    token_count: int
    code_block_id: str | None = None
    part_no: int | None = None


def passage_tokens(embedder: Embedder, text: str) -> int:
    """Include prefix and model special tokens in every budget."""
    return embedder.count_tokens("passage: " + text)


def _fit(text: str, start: int, budget: int, embedder: Embedder) -> int:
    low, high = start, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if passage_tokens(embedder, text[start:middle]) <= budget:
            low = middle
        else:
            high = middle - 1
    return low


def _text_chunks(page: Page, lines: list[Line], embedder: Embedder) -> list[ChunkDraft]:
    source_start, source_end = lines[0].start, lines[-1].end
    text = page.text[source_start:source_end]
    chunks = []
    start = 0
    while start < len(text):
        if not text[start:].strip():
            break
        end = _fit(text, start, 350, embedder)
        if end <= start:
            raise ValueError("Không thể chia văn bản trong giới hạn token.")
        if end < len(text):
            preferred = [m.end() for m in re.finditer(r"[.!?](?:\s+|$)|\n", text[start:end])]
            if preferred and preferred[-1] >= (end - start) // 2:
                end = start + preferred[-1]
            else:
                words = list(re.finditer(r"\s+", text[start:end]))
                if words:
                    end = start + words[-1].end()
        value = text[start:end]
        chunks.append(
            ChunkDraft(
                "text",
                page.index,
                page.index,
                page.label,
                source_start + start,
                source_start + end,
                value,
                passage_tokens(embedder, value),
            )
        )
        if end == len(text):
            break
        # Longest suffix with about 50 content tokens, aligned to a word boundary.
        low, high = start + 1, end
        while low < high:
            mid = (low + high) // 2
            if embedder.count_tokens(text[mid:end]) > 52:
                low = mid + 1
            else:
                high = mid
        boundary = re.search(r"\s+", text[low:end])
        start = low + boundary.end() if boundary else end
    return chunks


_FUNCTION = re.compile(
    r"^\s*(?!(?:if|for|while|switch|return)\b)[\w*]+(?:\s+[\w*]+)+\s*\([^;]*\)\s*\{?\s*$"
)


def _code_chunks(items: list[tuple[Page, Line]], embedder: Embedder) -> list[ChunkDraft]:
    result: list[ChunkDraft] = []
    start = 0
    declaration: str | None = None
    while start < len(items):
        prefix = (declaration + "\n") if declaration is not None and start else ""
        end = start
        while end < len(items):
            value = prefix + "\n".join(line.text for _, line in items[start : end + 1])
            if passage_tokens(embedder, value) > 480:
                break
            end += 1
        if end == start:
            raise ValueError("Một dòng mã vượt giới hạn 480 token; hãy chia dòng trong nguồn.")
        if end < len(items):
            breaks = [
                i + 1
                for i in range(start, end)
                if not items[i][1].text.strip() or items[i][1].text.strip() == "}"
            ]
            if breaks and breaks[-1] > start:
                end = breaks[-1]
        first_page, first_line = items[start]
        last_page, last_line = items[end - 1]
        value = prefix + "\n".join(line.text for _, line in items[start:end])
        # Cross-page offsets describe only the portion on the starting page.
        char_end = max(
            line.end for page, line in items[start:end] if page.index == first_page.index
        )
        result.append(
            ChunkDraft(
                "code",
                first_page.index,
                last_page.index,
                first_page.label,
                first_line.start,
                char_end,
                value,
                passage_tokens(embedder, value),
                first_line.code_block_id,
                len(result) + 1,
            )
        )
        for _, line in items[start:end]:
            if _FUNCTION.match(line.text):
                declaration = line.text
        start = end
    return result


def chunk_document(document: Document, embedder: Embedder) -> list[ChunkDraft]:
    items = [(page, line) for page in document.pages for line in page.lines]
    result = []
    i = 0
    while i < len(items):
        page, line = items[i]
        j = i + 1
        if line.is_code:
            while (
                j < len(items)
                and items[j][1].is_code
                and (items[j][1].code_block_id == line.code_block_id)
            ):
                j += 1
            result.extend(_code_chunks(items[i:j], embedder))
        else:
            while j < len(items) and items[j][0].index == page.index and not items[j][1].is_code:
                j += 1
            result.extend(_text_chunks(page, [item[1] for item in items[i:j]], embedder))
        i = j
    return _merge_small_text(result, embedder)


def _merge_small_text(chunks: list[ChunkDraft], embedder: Embedder) -> list[ChunkDraft]:
    """Merge small prose islands into the adjacent prose on the same page.

    The merged text omits intervening code; offsets bound both source excerpts
    in the canonical page, because the v0 schema has only one character interval.
    """
    islands = [
        chunk
        for i, chunk in enumerate(chunks)
        if chunk.kind == "text"
        and chunk.token_count < 40
        and 0 < i < len(chunks) - 1
        and chunks[i - 1].kind == chunks[i + 1].kind == "code"
        and chunks[i - 1].page_index_end == chunk.page_index == chunks[i + 1].page_index
    ]
    result = list(chunks)
    for island in islands:
        index = next(i for i, chunk in enumerate(result) if chunk is island)
        before = next(
            (
                c
                for c in reversed(result[:index])
                if c.kind == "text" and c.page_index == island.page_index
            ),
            None,
        )
        after = next(
            (
                c
                for c in result[index + 1 :]
                if c.kind == "text" and c.page_index == island.page_index
            ),
            None,
        )
        for target in (before, after):
            if target is None:
                continue
            first, second = sorted((island, target), key=lambda c: c.char_start)
            text = first.text + "\n" + second.text
            count = passage_tokens(embedder, text)
            if count > 350:
                continue
            target.text = text
            target.token_count = count
            target.char_start = min(first.char_start, second.char_start)
            target.char_end = max(first.char_end, second.char_end)
            result.pop(index)
            break
    return sorted(result, key=lambda c: (c.page_index, c.char_start))
