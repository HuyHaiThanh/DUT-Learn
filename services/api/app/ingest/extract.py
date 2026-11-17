"""Page text is the canonical NFC text used by chunk character offsets."""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import pymupdf
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExtractSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DUT_", env_file=".env", extra="ignore")
    space_gap_ratio: float = Field(default=0.15, ge=0)


@dataclass
class Line:
    text: str
    start: int = 0
    end: int = 0
    is_code: bool = False
    code_block_id: str | None = None


@dataclass
class Page:
    index: int
    label: str
    lines: list[Line]
    text: str = ""

    def __post_init__(self) -> None:
        offset = 0
        for line in self.lines:
            line.text = unicodedata.normalize("NFC", line.text)
            line.start = offset
            line.end = offset + len(line.text)
            offset = line.end + 1
        self.text = "\n".join(line.text for line in self.lines)


@dataclass
class Document:
    pages: list[Page]
    glued_tokens_before: int = 0
    glued_tokens_after: int = 0
    reading_order_warnings: list[int] = field(default_factory=list)


_GLUED = re.compile(r"[ảẳẩẻểỉỏổởủửỷãẵẫẽễĩõỗỡũữỹ][bdđfjklqrsvwxz]", re.IGNORECASE)
_C_KEYWORD = re.compile(
    r"^\s*(?:#|(?:int|char|float|double|long|short|unsigned|signed|void|struct|typedef|"
    r"const|static|extern|enum|union|volatile|for|while|do|if|else|switch|case|default|"
    r"return|break|continue)\b)"
)
_C_CALL = re.compile(r"\b[A-Za-z_][A-Za-z_0-9]*\s*\([^)]*\)")
_FOOTER = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")
_C_STRING = re.compile(r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' """, re.VERBOSE)


def _c_signal(text: str) -> bool:
    if any(marker in text for marker in (";", "{", "}", "/*", "*/", "//")):
        return True
    # Accented Vietnamese explanations can contain keywords and calls, e.g. max(a, b).
    if any(char.isalpha() and not char.isascii() for char in text):
        return False
    return bool(_C_KEYWORD.search(text) or _C_CALL.search(text))


def _comment_continues(text: str, in_comment: bool) -> bool:
    # Quoted comment markers and // comments must not open a multiline comment.
    for marker in re.finditer(r"/\*|\*/|//", _C_STRING.sub("", text)):
        if marker[0] == "//" and not in_comment:
            break
        if marker[0] == "/*":
            in_comment = True
        elif marker[0] == "*/":
            in_comment = False
    return in_comment


def glued_tokens(text: str) -> int:
    return len(_GLUED.findall(unicodedata.normalize("NFC", text)))


def _column_order(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recursive XY cut: whole columns before moving right; headers form bands."""
    if len(blocks) < 2:
        return blocks
    by_y = sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
    width = max(b["bbox"][2] for b in blocks) - min(b["bbox"][0] for b in blocks)
    # A spanning heading/footer must not force the body back into row-major order.
    first, last = by_y[0], by_y[-1]
    if first["bbox"][2] - first["bbox"][0] > 0.7 * width and (
        first["bbox"][3] <= min(b["bbox"][1] for b in by_y[1:]) + 2
    ):
        return [first, *_column_order(by_y[1:])]
    if last["bbox"][2] - last["bbox"][0] > 0.7 * width and (
        last["bbox"][1] >= max(b["bbox"][3] for b in by_y[:-1]) - 2
    ):
        return [*_column_order(by_y[:-1]), last]
    for axis in (0, 1):
        ordered = sorted(blocks, key=lambda b: b["bbox"][axis])
        edge = ordered[0]["bbox"][axis + 2]
        for i in range(1, len(ordered)):
            if ordered[i]["bbox"][axis] > edge + 2:
                return _column_order(ordered[:i]) + _column_order(ordered[i:])
            edge = max(edge, ordered[i]["bbox"][axis + 2])
    return sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))


def _overlap_warning(blocks: list[dict[str, Any]]) -> bool:
    for i, first in enumerate(blocks):
        a = first["bbox"]
        for second in blocks[i + 1 :]:
            b = second["bbox"]
            if min(a[2], b[2]) - max(a[0], b[0]) > 2 and (min(a[3], b[3]) - max(a[1], b[1]) > 2):
                return True
    return False


def _pdf_line(raw: dict[str, Any], ratio: float) -> tuple[Line, str]:
    restored: list[str] = []
    original: list[str] = []
    previous: dict[str, Any] | None = None
    mono = total = 0
    for span in raw["spans"]:
        is_mono = bool(span["flags"] & 8) or bool(
            re.search("Courier|Mono|Consol", span["font"], re.IGNORECASE)
        )
        for char in span["chars"]:
            value = char["c"]
            original.append(value)
            if (
                previous is not None
                and restored
                and not restored[-1].isspace()
                and (
                    not value.isspace()
                    and char["bbox"][0] - previous["bbox"][2] > ratio * span["size"]
                )
            ):
                restored.append(" ")
            restored.append(value)
            if not value.isspace():
                total += 1
                mono += is_mono
            previous = char
    return Line("".join(restored), is_code=bool(total and mono > total / 2)), "".join(original)


def _mark_pdf_code(pages: list[Page]) -> None:
    lines = [line for page in pages for line in page.lines]
    candidates = []
    in_comment = False
    for line in lines:
        candidate = line.is_code or in_comment or _c_signal(line.text)
        candidates.append(candidate)
        if candidate:
            in_comment = _comment_continues(line.text, in_comment)
    run: list[Line] = []
    # Look ahead over blank lines; a weak signature/loop can start a run when
    # followed by another C line. Keep comment bodies and all C signals in that run.
    sentinel = Line("")
    for line, candidate in zip([*lines, sentinel], [*candidates, False], strict=True):
        if candidate or (run and not line.text.strip() and line is not sentinel):
            run.append(line)
        else:
            while run and not run[-1].text.strip():
                run.pop()
            if sum(bool(item.text.strip()) for item in run) >= 2 or any(
                item.is_code for item in run
            ):
                for item in run:
                    item.is_code = True
            run = []
    block = 0
    in_code = False
    for line in lines:
        if line.is_code:
            if not in_code:
                block += 1
            line.code_block_id = f"pdf-code-{block}"
        in_code = line.is_code


def extract_pdf(data: bytes, *, gap_ratio: float | None = None) -> Document:
    if not data.startswith(b"%PDF"):
        raise ValueError("Tệp PDF không hợp lệ.")
    ratio = ExtractSettings().space_gap_ratio if gap_ratio is None else gap_ratio
    pages: list[Page] = []
    before = 0
    warnings: list[int] = []
    with pymupdf.open(stream=data, filetype="pdf") as pdf:  # type: ignore[no-untyped-call]
        if pdf.needs_pass:
            raise ValueError("Không hỗ trợ PDF được bảo vệ bằng mật khẩu.")
        for index, page in enumerate(pdf):
            # Disable MuPDF's synthetic spaces: measure gaps ourselves, retaining real spaces.
            raw = page.get_text(
                "rawdict", flags=pymupdf.TEXTFLAGS_RAWDICT | pymupdf.TEXT_INHIBIT_SPACES
            )
            # MuPDF can group two distant columns on the same baseline into one block.
            # Preserve its lines, but allow the column cut to separate such a block.
            blocks = [
                {"bbox": line["bbox"], "lines": [line]}
                for block in raw["blocks"]
                if block["type"] == 0
                for line in block["lines"]
            ]
            if _overlap_warning(blocks):
                warnings.append(index)
            lines = []
            for block in _column_order(blocks):
                for raw_line in block["lines"]:
                    line, original = _pdf_line(raw_line, ratio)
                    if _FOOTER.fullmatch(line.text):
                        continue  # Filter before Page calculates canonical character offsets.
                    before += glued_tokens(original)
                    lines.append(line)
            pages.append(Page(index, page.get_label() or str(index + 1), lines))
    _mark_pdf_code(pages)
    return Document(pages, before, sum(glued_tokens(p.text) for p in pages), warnings)


def extract_text(data: bytes, *, page_chars: int = 3000) -> Document:
    text = (
        unicodedata.normalize("NFC", data.decode("utf-8-sig"))
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if page_chars <= 0:
        raise ValueError("Kích thước trang phải dương.")
    # Prefer paragraph boundaries, with a line/word fallback for oversized paragraphs.
    parts: list[str] = []
    pagination_fenced = False
    while len(text) > page_chars:
        cut = text.rfind("\n\n", 0, page_chars + 1)
        if cut < page_chars // 2:
            cut = text.rfind("\n", 0, page_chars + 1)
        if cut < page_chars // 2:
            word_cut = text.rfind(" ", 0, page_chars + 1)
            in_code = pagination_fenced
            for value in text[: max(0, word_cut)].split("\n"):
                if re.match(r"^\s*```", value):
                    in_code = not in_code
            if not in_code:
                cut = word_cut
        if cut < 1:
            # Never cut a code line or a word silently; an oversized code line fails chunking.
            cut = text.find("\n", page_chars)
            if cut < 0:
                cut = len(text)
        for value in text[:cut].split("\n"):
            if re.match(r"^\s*```", value):
                pagination_fenced = not pagination_fenced
        parts.append(text[:cut])
        text = text[cut:]
        if text.startswith("\n"):
            text = text[1:]
    parts.append(text)
    pages = []
    fenced = False
    block = 0
    for index, part in enumerate(parts):
        lines = []
        for value in part.split("\n"):
            fence = bool(re.match(r"^\s*```", value))
            if fence:
                fenced = not fenced
                if fenced:
                    block += 1
            lines.append(
                Line(
                    value,
                    is_code=fenced and not fence,
                    code_block_id=f"fence-{block}" if fenced and not fence else None,
                )
            )
        pages.append(Page(index, str(index + 1), lines))
    count = sum(glued_tokens(p.text) for p in pages)
    return Document(pages, count, count)
