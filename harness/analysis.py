"""Utilitários das análises offline (labs 03/07/08) em cima do run do lab 00."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ["department", "urgency", "refund_wanted", "churn_threat", "has_bug"]


def latest_run(lab: str = "00_dataset_run") -> tuple[Path, list[dict]]:
    files = sorted((ROOT / "results" / lab).glob("*.jsonl"))
    if not files:
        raise SystemExit(f"sem resultados em results/{lab} — rode `uv run lab 00` antes")
    return files[-1], [json.loads(l) for l in files[-1].read_text(encoding="utf-8").splitlines()]


def acc(hits: list[bool]) -> float:
    return sum(hits) / len(hits) if hits else float("nan")
