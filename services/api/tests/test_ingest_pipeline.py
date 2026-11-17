import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

from app.ingest.chunk import chunk_document
from app.ingest.extract import Document, Line, Page, extract_pdf, extract_text, glued_tokens
from app.ingest.quality import quality_report
from app.rag.embedder import E5Embedder, FakeEmbedder


@pytest.fixture
def embedder():
    return FakeEmbedder()


def pdf_bytes(tmp_path, pages):
    path = tmp_path / "sample.pdf"
    with pymupdf.open() as pdf:
        for entries in pages:
            page = pdf.new_page()
            for x, y, text, font in entries:
                page.insert_text((x, y), text, fontname=font, fontsize=11)
        pdf.save(path)
    return path.read_bytes()


def test_pdf_restores_coordinate_gaps_without_splitting_normal_text(tmp_path):
    path = tmp_path / "gaps.pdf"
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    # Use a Unicode font for the Vietnamese glued-token regression on Windows.
    font = pymupdf.Font(fontfile=str(font_path)) if font_path.exists() else pymupdf.Font("helv")
    first, second = ("sử", "dụng") if font_path.exists() else ("use", "words")
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        if font_path.exists():
            page.insert_font(fontname="unicode", fontfile=str(font_path))
        name = "unicode" if font_path.exists() else "helv"
        x = 40
        for index, char in enumerate(first + second):
            # Separate the two words by 0.2 em; the PDF contains no space glyph.
            if index == len(first):
                x += 2.4
            page.insert_text((x, 60), char, fontname=name, fontsize=12)
            x += font.text_length(char, fontsize=12)
        page.insert_text((40, 100), "normal words remain intact", fontname=name, fontsize=12)
        pdf.save(path)
    document = extract_pdf(path.read_bytes())
    assert f"{first} {second}" in document.pages[0].text
    assert "normal words remain intact" in " ".join(document.pages[0].text.split())
    if font_path.exists():
        assert document.glued_tokens_before == 1
        assert document.glued_tokens_after == 0


def test_pdf_labels_nfc_and_empty_page(tmp_path):
    path = tmp_path / "labels.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.set_page_labels([{"startpage": 0, "prefix": "Intro-", "style": "r", "firstpagenum": 1}])
        pdf.save(path)
    doc = extract_pdf(path.read_bytes())
    assert doc.pages[0].label == "Intro-i"
    assert quality_report(doc, [], "fake", 0)["empty_pages"] == [0]
    assert extract_text("su\u031b\u0309 dụng".encode()).pages[0].text == "sử dụng"
    assert glued_tokens("sửdụng mãlệnh thửnghiệm") == 2


@pytest.mark.parametrize("font", ["cour", "helv"])
def test_pdf_code_font_and_c_fallback(tmp_path, embedder, font):
    data = pdf_bytes(
        tmp_path,
        [
            [
                (40, 50, "int main()", font),
                (40, 70, "{", font),
                (40, 90, 'printf("Hello");', font),
                (40, 110, "}", font),
            ]
        ],
    )
    chunks = chunk_document(extract_pdf(data), embedder)
    assert len(chunks) == 1
    assert chunks[0].kind == "code" and chunks[0].part_no == 1
    assert "int main()" in chunks[0].text


def test_single_prose_semicolon_is_not_code(tmp_path, embedder):
    doc = extract_pdf(pdf_bytes(tmp_path, [[(40, 50, "An ordinary sentence;", "helv")]]))
    assert [c.kind for c in chunk_document(doc, embedder)] == ["text"]


def test_pdf_code_continues_across_pages(tmp_path, embedder):
    data = pdf_bytes(
        tmp_path,
        [
            [(40, 50, "int main() {", "cour"), (40, 70, "int x = 1;", "cour")],
            [(40, 50, 'printf("%d", x);', "cour"), (40, 70, "}", "cour")],
        ],
    )
    doc = extract_pdf(data)
    chunks = chunk_document(doc, embedder)
    assert len(chunks) == 1 and chunks[0].kind == "code"
    assert (chunks[0].page_index, chunks[0].page_index_end) == (0, 1)
    assert chunks[0].char_end == len(doc.pages[0].text)


def test_two_columns_read_down_left_then_right_and_warn_on_overlap(tmp_path):
    data = pdf_bytes(
        tmp_path,
        [
            [
                (40, 50, "Left one", "helv"),
                (320, 50, "Right one", "helv"),
                (40, 90, "Left two", "helv"),
                (320, 90, "Right two", "helv"),
            ]
        ],
    )
    doc = extract_pdf(data)
    assert doc.pages[0].text == "Left one\nLeft two\nRight one\nRight two"
    assert not doc.reading_order_warnings
    data = pdf_bytes(
        tmp_path,
        [
            [
                (40, 50, "Left column reaches into another column", "helv"),
                (80, 55, "Overlapping column", "helv"),
            ]
        ],
    )
    assert extract_pdf(data).reading_order_warnings == [0]


def test_text_budget_overlap_offsets_and_page_boundaries(embedder):
    pages = [
        Page(i, str(i + 1), [Line(" ".join(f"p{i}word{j}" for j in range(900)))]) for i in range(2)
    ]
    chunks = chunk_document(Document(pages), embedder)
    assert len(chunks) >= 6
    for chunk in chunks:
        assert chunk.token_count <= 350
        assert chunk.page_index == chunk.page_index_end
        assert pages[chunk.page_index].text[chunk.char_start : chunk.char_end] == chunk.text
    for previous, current in zip(chunks, chunks[1:]):
        if previous.page_index == current.page_index:
            shared = set(previous.text.split()) & set(current.text.split())
            assert 45 <= len(shared) <= 52


def test_pdf_column_order_with_spanning_header_footer(tmp_path):
    heading = "A full width heading extending across both columns"
    footer = "A full width footer extending across both columns"
    data = pdf_bytes(
        tmp_path,
        [
            [
                (40, 30, heading, "helv"),
                (40, 70, "Left one", "helv"),
                (320, 70, "Right one", "helv"),
                (40, 100, "Left two", "helv"),
                (320, 100, "Right two", "helv"),
                (40, 140, footer, "helv"),
            ]
        ],
    )
    assert extract_pdf(data).pages[0].text.splitlines() == [
        heading,
        "Left one",
        "Left two",
        "Right one",
        "Right two",
        footer,
    ]


def test_text_prefers_sentence_or_line_boundaries(embedder):
    text = "\n".join(" ".join([str(i)] * 80) + "." for i in range(12))
    chunks = chunk_document(Document([Page(0, "1", [Line(text)])]), embedder)
    assert all(c.text.endswith("\n") for c in chunks[:-1])


def test_long_code_splits_on_lines_with_declaration_context(embedder):
    lines = ["int calculate(int x) {", *[f"x = x + {i};" for i in range(240)], "}"]
    source = "Intro\n```c\n" + "\n".join(lines) + "\n```\nEnd"
    doc = extract_text(source.encode())
    chunks = [c for c in chunk_document(doc, embedder) if c.kind == "code"]
    assert len(chunks) > 1
    assert len({c.code_block_id for c in chunks}) == 1
    assert [c.part_no for c in chunks] == list(range(1, len(chunks) + 1))
    actual = []
    for index, chunk in enumerate(chunks):
        assert chunk.token_count <= 480
        values = chunk.text.splitlines()
        assert values[0] == lines[0]
        actual.extend(values[1:] if index else values)
    assert actual == lines
    report = quality_report(doc, chunks, "fake", 12)
    assert report["code_blocks"] == {"total": 1, "split": 1}


def test_short_fences_and_separate_blocks(embedder):
    doc = extract_text(b"Text\n```c\nint x = 1;\n```\n\n```c\nint y = 2;\n```\n")
    chunks = [c for c in chunk_document(doc, embedder) if c.kind == "code"]
    assert [c.text for c in chunks] == ["int x = 1;", "int y = 2;"]
    assert len({c.code_block_id for c in chunks}) == 2


def test_txt_pagination_at_paragraph_boundaries_and_fence_carry(embedder):
    paragraphs = [f"Paragraph {i} " + "word " * 100 for i in range(14)]
    doc = extract_text("\n\n".join(paragraphs).encode())
    assert len(doc.pages) == 3
    assert all(2000 <= len(p.text) <= 3000 for p in doc.pages[:-1])
    assert all("Paragraph" in p.text for p in doc.pages)
    source = "```c\n" + "\n".join(f"x = {i};" for i in range(70)) + "\n```"
    doc = extract_text(source.encode(), page_chars=200)
    chunks = [c for c in chunk_document(doc, embedder) if c.kind == "code"]
    assert len(chunks) == 1 and chunks[0].page_index_end > 0
    assert chunks[0].text.splitlines() == source.splitlines()[1:-1]


@pytest.mark.parametrize("words", [600, 4000])
def test_oversized_code_line_fails_instead_of_truncating(embedder, words):
    with pytest.raises(ValueError, match="480"):
        chunk_document(extract_text(("```\n" + "x " * words + "\n```").encode()), embedder)


def test_fake_embeddings_deterministic_and_normalized(embedder):
    first = embedder.embed_passages(["hello world", "", "hello world"])
    assert first[0] == first[2] and first[0] != embedder.embed_query("hello world")
    for vector in first:
        assert len(vector) == 384
        assert math.isclose(sum(v * v for v in vector), 1)
    assert embedder.count_tokens("passage: hello world") == 5


def test_e5_lazy_threadsafe_loading_prefixes_batches_and_token_limit(monkeypatch):
    calls = []
    created = []
    fake = FakeEmbedder()

    class Model:
        def __init__(self, name, device):
            created.append((name, device))
            self.tokenizer = fake.tokenizer

        def get_sentence_embedding_dimension(self):
            return 384

        def encode(self, texts, **kwargs):
            calls.append((texts, kwargs, self.max_seq_length))
            return SimpleNamespace(tolist=lambda: [fake.embed_query(t) for t in texts])

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Model)
    )
    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    )
    monkeypatch.setattr(E5Embedder, "_models", {})
    models = [E5Embedder("test-e5") for _ in range(5)]
    assert not created
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda m: m.embed_passages(["hi"]), models))
    models[0].embed_query("question")
    assert created == [("test-e5", "cpu")]
    assert calls[0][0] == ["passage: hi"] and calls[-1][0] == ["query: question"]
    assert all(c[1]["batch_size"] == 32 and c[1]["normalize_embeddings"] for c in calls)
    assert all(c[2] == 512 for c in calls)
    with pytest.raises(ValueError, match="512"):
        models[0].embed_passages(["token " * 512])


@pytest.mark.model
@pytest.mark.skipif(
    os.environ.get("DUT_RUN_MODEL_TESTS") != "1", reason="DUT_RUN_MODEL_TESTS=1 required"
)
def test_real_e5_model():
    model = E5Embedder()
    vectors = model.embed_passages(["Hàm trong ngôn ngữ C.", "Con trỏ và bộ nhớ."])
    vectors.append(model.embed_query("Hàm là gì?"))
    assert model.count_tokens("passage: Hàm trong C.") <= 512
    for vector in vectors:
        assert len(vector) == 384 and all(math.isfinite(v) for v in vector)
        assert math.isclose(sum(v * v for v in vector), 1, abs_tol=1e-4)
