import re
from collections.abc import Iterator

LIMITATION = (
    "Câu trả lời chưa dẫn được nguồn cụ thể trong học liệu; hãy đối chiếu lại với giáo trình."
)

# Match a whole adjacent citation chain so [1][2] is accepted, while the
# identifier/closing-bracket boundary excludes all of a[1][2] and f(x)[0].
# The model sometimes prefixes the number ("[n1]", "[nguồn 2]"); accept those forms too.
# Live Qwen2.5 output also glues citations to list numbers ("1[4]") or accented words
# ("chỉ[1]"), so only an ASCII identifier character, "_", "]" or ")" before "[" marks
# array syntax (a[1], m[1][2], f(x)[0]). Trade-off: "arr1[2]" outside code would be read
# as a citation; code is normally fenced or in backticks, which are never parsed.
CITATION_CHAIN = re.compile(
    r"(?<![A-Za-z_\]\)])"
    r"(?:\[\s*(?:(?:n|nguồn)\s*)?\d+(?:\s*[,–-]\s*(?:(?:n|nguồn)\s*)?\d+)*\s*\])+",
    re.IGNORECASE,
)


def code_spans(text: str) -> Iterator[tuple[int, int]]:
    """Protect backtick spans and fences, including an unfinished fenced block."""
    runs = list(re.finditer(r"`+", text))
    index = 0
    while index < len(runs):
        opening = runs[index]
        width = len(opening.group())
        closing_index = next(
            (
                i
                for i in range(index + 1, len(runs))
                if len(runs[i].group()) == width or (width >= 3 and len(runs[i].group()) > width)
            ),
            None,
        )
        if closing_index is not None:
            yield opening.start(), runs[closing_index].end()
            index = closing_index + 1
        elif width >= 3:
            yield opening.start(), len(text)
            return
        else:
            index += 1


def parse_citations(answer: str, count: int) -> tuple[str, list[int]]:
    valid: set[int] = set()

    def rewrite(match: re.Match[str]) -> str:
        numbers: list[int] = []
        for item in re.finditer(r"(\d+)(?:\s*[-–]\s*(\d+))?", match.group()):
            start = int(item.group(1))
            if item.group(2) is not None:
                end = int(item.group(2))
                numbers.extend(range(max(1, start), min(count, end) + 1))
            else:
                numbers.append(start)
        numbers = list(dict.fromkeys(n for n in numbers if 1 <= n <= count))
        valid.update(numbers)
        return "".join(f"[{n}]" for n in numbers)

    parts: list[str] = []
    cursor = 0
    for start, end in code_spans(answer):
        parts.append(CITATION_CHAIN.sub(rewrite, answer[cursor:start]))
        parts.append(answer[start:end])
        cursor = end
    parts.append(CITATION_CHAIN.sub(rewrite, answer[cursor:]))
    return "".join(parts), sorted(valid)
