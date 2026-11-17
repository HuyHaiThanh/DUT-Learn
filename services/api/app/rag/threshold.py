"""Pure evidence gating and dev-set threshold calibration."""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rag.retriever import RetrievalResult


@dataclass(frozen=True)
class SweepRow:
    threshold: float
    true_refusal: float
    false_refusal: float
    n_pos: int
    n_neg: int


@dataclass(frozen=True)
class SweepResult:
    threshold: float
    rows: list[SweepRow]
    auroc: float | None
    warning: str | None = None


def passes_evidence_gate(result: "RetrievalResult", threshold: float) -> bool:
    return result.top_cosine is not None and result.top_cosine >= threshold


def sweep_thresholds(
    pos: list[float], neg: list[float], *, max_false_refusal: float = 0.10
) -> SweepResult:
    if not 0 <= max_false_refusal <= 1:
        raise ValueError("max_false_refusal phải thuộc [0, 1].")
    if any(not math.isfinite(score) for score in [*pos, *neg]):
        raise ValueError("Điểm cosine phải hữu hạn.")
    rows = [
        SweepRow(
            t,
            sum(score < t for score in neg) / len(neg) if neg else 0.0,
            sum(score < t for score in pos) / len(pos) if pos else 0.0,
            len(pos),
            len(neg),
        )
        for t in sorted({0.0, *pos, *neg})
    ]
    if not pos or not neg:
        return SweepResult(0.0, rows, None, "Thiếu mẫu dương hoặc âm; chưa hiệu chỉnh ngưỡng.")
    best = min(
        (row for row in rows if row.false_refusal <= max_false_refusal),
        key=lambda row: (-row.true_refusal, row.threshold),
    )
    auroc = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))
    return SweepResult(best.threshold, rows, auroc)
