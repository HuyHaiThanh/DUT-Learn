from pathlib import Path

import pymupdf
import pytest

from app.ingest.chunk import chunk_document
from app.ingest.extract import extract_pdf
from app.ingest.quality import quality_report
from app.rag.embedder import FakeEmbedder


def generated_pdf(tmp_path, pages, *, label=None):
    path = tmp_path / "regression.pdf"
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    font_path = next(path for path in candidates if path.exists())
    font = pymupdf.Font(fontfile=str(font_path))
    with pymupdf.open() as pdf:
        for lines in pages:
            page = pdf.new_page(width=2400, height=max(842, 100 + 18 * len(lines)))
            page.insert_font(fontname="proportional", fontbuffer=font.buffer)
            for index, line in enumerate(lines):
                page.insert_text((40, 50 + 18 * index), line, fontname="proportional", fontsize=11)
            page.insert_text(
                (250, page.rect.height - 30), "47/199", fontname="proportional", fontsize=11
            )
        if label:
            pdf.set_page_labels([{"startpage": 0, "prefix": label}])
        pdf.save(path)
    return extract_pdf(path.read_bytes())


PROGRAMS = [
    [
        [
            "int main() {",
            "int x,y;",
            "x =10; /*Gán hằng số 10 cho biến x*/",
            "y = 2*x; /*Tính giá trị y*/",
            "return 0;",
            "}",
        ]
    ],
    [
        [
            "#include <stdio.h>",
            "#include <conio.h>",
            "int max(int a, int b)",
            "{",
            "return (a>b) ? a:b;",
        ],
        ["}", "int main()", "{", 'printf("%d", max(1,2));', "return 0;", "}"],
    ],
    [
        [
            "void ReadFile(char *FileName)",
            "{",
            "FILE *f;",
            'f = fopen(FileName, "r");',
            "/* Đọc các phần tử",
            "vào mảng dữ liệu",
            "*/",
            "for(i=1;i<=n;i++)",
            "{",
            'fscanf(f, "%d", &a[i]);',
            "}",
            "// Đóng tệp sau khi đọc",
            "fclose(f);",
            "}",
        ]
    ],
]


@pytest.mark.parametrize("pages", PROGRAMS, ids=["page49", "page100-101", "page189"])
def test_voer_program_stays_one_code_chunk(tmp_path, pages):
    document = generated_pdf(tmp_path, pages)
    chunks = chunk_document(document, FakeEmbedder())
    assert [chunk.kind for chunk in chunks] == ["code"]
    chunk = chunks[0]
    assert chunk.page_index == 0 and chunk.page_index_end == len(pages) - 1
    assert chunk.token_count <= 480
    assert len(chunk.text.splitlines()) == sum(len(lines) for lines in pages)
    assert "47/199" not in chunk.text


@pytest.mark.parametrize("first", ["void InKT(char ch)", "for(i=1;i<=n;i++)", "while(i<n)"])
def test_function_or_loop_can_start_code_block(tmp_path, first):
    document = generated_pdf(tmp_path, [[first, "{", 'printf("%d", i);', "}"]])
    chunks = chunk_document(document, FakeEmbedder())
    assert len(chunks) == 1 and chunks[0].kind == "code"
    assert first in chunks[0].text.replace("\xa0", " ")


@pytest.mark.parametrize("label,expected", [(None, "1"), ("PDF-label", "PDF-label")])
def test_footer_removed_before_offsets_with_pdf_label_precedence(tmp_path, label, expected):
    document = generated_pdf(tmp_path, [["Văn bản trước chân trang."]], label=label)
    page = document.pages[0]
    assert "47/199" not in page.text
    assert page.label == expected
    assert all(page.text[line.start : line.end] == line.text for line in page.lines)
    chunks = chunk_document(document, FakeEmbedder())
    assert chunks and all(page.text[c.char_start : c.char_end] == c.text for c in chunks)


def test_vietnamese_prose_with_parentheses_and_commas_stays_text(tmp_path):
    prose = [
        "Ví dụ 2: Xét hàm max(a, b), giá trị lớn nhất của hai số.",
        "for là từ khóa lặp (trong ngôn ngữ C), được giải thích ở đây.",
        "int là kiểu số nguyên, có thể biểu diễn số âm (và số dương).",
        "Trong ví dụ (a, b), giá trị được so sánh theo điều kiện.",
    ]
    document = generated_pdf(
        tmp_path,
        [
            [
                "int main() {",
                "return 0;",
                "}",
                *prose,
                "void InKT(char ch)",
                "{",
                "putchar(ch);",
                "}",
            ]
        ],
    )
    chunks = chunk_document(document, FakeEmbedder())
    text = "\n".join(c.text for c in chunks if c.kind == "text").replace("\xa0", " ")
    assert all(line in text for line in prose)
    assert all(
        not line.is_code
        for line in document.pages[0].lines
        if line.text.replace("\xa0", " ") in prose
    )


@pytest.mark.parametrize("destination", ["before", "after"])
def test_short_text_between_code_blocks_merges_with_nearest_prose(tmp_path, destination):
    intro = "Giải thích kiến thức " + "nội dung " * 28
    short = "Ví dụ 2: Minh họa cách gọi hàm."
    body = ["int main() {", "return 0;", "}", short, "void InKT(char ch)", "{", "putchar(ch);", "}"]
    lines = [intro, *body] if destination == "before" else [*body, intro]
    document = generated_pdf(tmp_path, [lines])
    chunks = chunk_document(document, FakeEmbedder())
    text = [c for c in chunks if c.kind == "text"]
    code = [c for c in chunks if c.kind == "code"]
    assert len(text) == 1
    assert short in text[0].text.replace("\xa0", " ")
    assert intro in text[0].text.replace("\xa0", " ")
    assert text[0].token_count <= 350 and text[0].page_index == text[0].page_index_end == 0
    assert len(code) == 2 and all(
        short not in c.text.replace("\xa0", " ") and intro not in c.text.replace("\xa0", " ")
        for c in code
    )
    sources = [
        line for line in document.pages[0].lines if line.text.replace("\xa0", " ") in (intro, short)
    ]
    assert len(sources) == 2
    assert text[0].char_start == min(line.start for line in sources)
    assert text[0].char_end == max(line.end for line in sources)


@pytest.mark.parametrize("separate_pages", [False, True])
def test_short_prose_never_exceeds_budget_or_merges_across_pages(tmp_path, separate_pages):
    intro = " ".join(f"word{i}" for i in range(340))
    # Keep PDF lines within the page's printable width.
    intro_lines = [" ".join(intro.split()[i : i + 8]) for i in range(0, 340, 8)]
    short = "Ví dụ ngắn " + "từ " * 20
    body = ["int main() {", "return 0;", "}", short, "int next() {", "return 1;", "}"]
    pages = [intro_lines, body] if separate_pages else [intro_lines + body]
    document = generated_pdf(tmp_path, pages)
    chunks = chunk_document(document, FakeEmbedder())
    text = [c for c in chunks if c.kind == "text"]
    assert len(text) == 2
    assert all(c.token_count <= 350 and c.page_index == c.page_index_end for c in text)
    assert any(c.text.replace("\xa0", " ").strip() == short.strip() for c in text)


def test_small_chunk_and_median_statistics_by_kind(tmp_path):
    document = generated_pdf(
        tmp_path, [["A short introduction.", "int main() {", "return 0;", "}"]]
    )
    chunks = chunk_document(document, FakeEmbedder())
    report = quality_report(document, chunks, "fake", 1)
    assert report["small_chunks"] == {"text": 1, "code": 1}
    assert report["token_median"] == {
        kind: next(c.token_count for c in chunks if c.kind == kind) for kind in ("text", "code")
    }
    empty = quality_report(document, [], "fake", 1)
    assert empty["small_chunks"] == {"text": 0, "code": 0}
    assert empty["token_median"] == {"text": 0, "code": 0}
