import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.rag import retriever as module
from app.rag.retriever import (
    AnswerableQuestion,
    Hit,
    Question,
    QuestionFile,
    RetrievalResult,
    page_metrics,
    run_questions,
)


def hit(page, end=None, score=0.8):
    return Hit(
        chunk_id=uuid4(),
        version_id=uuid4(),
        material_id=uuid4(),
        material_title="PRIVATE TITLE",
        kind="text",
        page_index=page,
        page_index_end=page if end is None else end,
        page_label=None,
        char_start=0,
        char_end=100,
        text="PRIVATE CHUNK " * 10,
        rank=1,
        cosine=score,
    )


def result(hits):
    return RetrievalResult(
        [replace(h, rank=i) for i, h in enumerate(hits, 1)],
        "dense",
        max((h.cosine for h in hits), default=None),
        {"embed": 1.0, "search": 2.0},
    )


def test_page_metrics_deduplicate_and_expand_cross_page():
    retrieval = result([hit(0), hit(0), hit(1, 3), hit(4), hit(5)])
    assert page_metrics(retrieval, [4]) == (1, 0.25)
    assert page_metrics(retrieval, [6]) == (0, 1 / 6)
    assert page_metrics(retrieval, [99]) == (0, 0)
    assert page_metrics(retrieval, [2, 4]) == (1, 0.5)
    assert page_metrics(result([hit(i) for i in range(12)]), [11]) == (0, 0)
    assert page_metrics(result([]), [1]) == (0, 0)


class StubRetriever:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def retrieve(self, db, **kwargs):
        self.calls.append(kwargs)
        return next(self.results)


def test_pilot_dev_trace_sweep_no_content(tmp_path, capsys):
    questions = QuestionFile.model_validate(
        {
            "e_r": [{"id": "p1", "question": "PRIVATE QUESTION", "accepted_pages": [4]}],
            "unanswerable": [{"id": "n1", "question": "PRIVATE NEGATIVE"}],
        }
    )
    stub = StubRetriever([result([hit(0), hit(0), hit(1, 3)]), result([hit(0, score=0.2)])])
    run_questions(
        None,
        retriever=stub,
        user=SimpleNamespace(id=uuid4()),
        class_id=uuid4(),
        questions=questions,
        k=10,
        out=tmp_path,
        dataset_hash="testhash",
    )
    output = capsys.readouterr().out
    assert "Hit@5=1.0000" in output and "MRR@10=0.2500" in output
    assert "PRIVATE QUESTION" not in output
    negative_output = output.split("id=n1", 1)[1]
    assert "page=" not in negative_output and "PRIVATE CHUNK" not in negative_output
    assert all(
        c["prefer_material_id"] is None and c["prefer_page_index"] is None for c in stub.calls
    )
    raw_trace = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert "PRIVATE" not in raw_trace
    traces = [json.loads(line) for line in raw_trace.splitlines()]
    assert len(traces) == 2 and traces[0]["request_id"] != traces[1]["request_id"]
    entry = traces[0]["hits"][0]
    assert set(entry) >= {
        "chunk_id",
        "version_id",
        "page_index",
        "rank",
        "cosine",
        "bm25_score",
        "rrf_score",
        "used_in_prompt",
    }
    assert entry["used_in_prompt"] is False and entry["bm25_score"] is None
    sweep = json.loads((tmp_path / "thresholds.json").read_text(encoding="utf-8"))
    assert sweep["threshold"] == 0.8 and sweep["auroc"] == 1
    assert sweep["dataset_sha256"] == "testhash"


def test_pilot_only_and_missing_scores_are_not_dropped(tmp_path, capsys):
    positive = AnswerableQuestion(id="p", question="synthetic", accepted_pages=[1])
    negative = Question(id="n", question="synthetic negative")
    kwargs = dict(db=None, user=None, class_id=uuid4(), k=10, out=tmp_path)
    run_questions(
        **kwargs,
        retriever=StubRetriever([result([])]),
        questions=QuestionFile(e_r=[positive]),
    )
    assert "Hit@5=0.0000" in capsys.readouterr().out
    run_questions(
        **kwargs,
        retriever=StubRetriever([result([]), result([])]),
        questions=QuestionFile(e_r=[positive], unanswerable=[negative]),
    )
    assert "top_cosine=null" in capsys.readouterr().out
    sweep = json.loads((tmp_path / "thresholds.json").read_text(encoding="utf-8"))
    assert sweep["threshold"] is None and sweep["warning"]


@pytest.mark.parametrize("bad", ["{}", '{"e_r": [{"id": "x"}]}', "not-json"])
def test_cli_invalid_json_no_input_echo(tmp_path, monkeypatch, capsys, bad):
    path = tmp_path / "questions.json"
    path.write_text(bad, encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "retriever",
            "--class-id",
            str(uuid4()),
            "--user-email",
            "user@example.test",
            "--questions",
            str(path),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 2
    assert bad not in capsys.readouterr().err


def test_cli_main_pilot_and_query(tmp_path, monkeypatch, capsys):
    class DB:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def scalar(self, statement):
            return SimpleNamespace(id=uuid4(), is_active=True)

    path = tmp_path / "pilot.json"
    path.write_text(
        json.dumps(
            {
                "e_r": [{"id": "pilot", "question": "synthetic", "accepted_pages": [1]}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "SessionLocal", DB)
    stub = StubRetriever([result([hit(0)]), result([hit(0)])])
    monkeypatch.setattr(module, "get_retriever", lambda settings: stub)
    common = ["retriever", "--class-id", str(uuid4()), "--user-email", "User@example.test"]
    monkeypatch.setattr("sys.argv", [*common, "--questions", str(path)])
    module.main()
    assert "Hit@5=1.0000" in capsys.readouterr().out
    assert stub.calls[0]["k"] == 10
    monkeypatch.setattr("sys.argv", [*common, "--query", "synthetic"])
    module.main()
    output = capsys.readouterr().out
    assert "page=1" in output and "Hit@5" not in output
