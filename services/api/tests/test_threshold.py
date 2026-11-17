import pytest

from app.rag.retriever import RetrievalResult
from app.rag.threshold import passes_evidence_gate, sweep_thresholds


@pytest.mark.parametrize(("score", "expected"), [(None, False), (0.5, True), (0.49, False)])
def test_gate(score, expected):
    result = RetrievalResult([], "dense", score, {"embed": 0, "search": 0})
    assert passes_evidence_gate(result, 0.5) is expected


def test_hand_calculated_sweep_constraint_and_ties():
    result = sweep_thresholds([0.4] + [0.8] * 9, [0.1, 0.3, 0.5, 0.9])
    assert result.threshold == 0.8
    assert [(r.threshold, r.true_refusal, r.false_refusal) for r in result.rows] == [
        (0, 0, 0),
        (0.1, 0, 0),
        (0.3, 0.25, 0),
        (0.4, 0.5, 0),
        (0.5, 0.5, 0.1),
        (0.8, 0.75, 0.1),
        (0.9, 0.75, 1),
    ]
    assert all((r.n_pos, r.n_neg) == (10, 4) for r in result.rows)
    strict = sweep_thresholds([0.4] + [0.8] * 9, [0.1, 0.3, 0.5, 0.9], max_false_refusal=0)
    assert strict.threshold == 0.4
    assert sweep_thresholds([0.8], [0.1]).threshold == 0.8
    assert sweep_thresholds([0.8], [0.8]).threshold == 0


@pytest.mark.parametrize(
    ("pos", "neg", "auc"),
    [([0.8, 0.9], [0.1, 0.2], 1), ([0.1, 0.2], [0.8, 0.9], 0), ([0.5], [0.5], 0.5)],
)
def test_auc(pos, neg, auc):
    assert sweep_thresholds(pos, neg).auroc == auc


@pytest.mark.parametrize(("pos", "neg"), [([0.5], []), ([], [0.5]), ([], [])])
def test_empty_samples_warn(pos, neg):
    result = sweep_thresholds(pos, neg)
    assert result.threshold == 0 and result.warning and result.auroc is None


def test_invalid_inputs_and_negative_scores():
    with pytest.raises(ValueError):
        sweep_thresholds([float("nan")], [0])
    with pytest.raises(ValueError):
        sweep_thresholds([0], [0], max_false_refusal=1.1)
    assert sweep_thresholds([-0.5], [-0.9]).threshold == -0.5
