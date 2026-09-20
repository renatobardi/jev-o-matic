import json
from pathlib import Path
from typing import Any

import pytest

from jevomatic_api.jev import Answer
from jevomatic_api.verdict import DEFAULT_T, clamp_t, verdict

CASES = json.loads((Path(__file__).parent / "verdict_cases.json").read_text(encoding="utf-8"))


def _answers(d: dict[str, list[Any]]) -> dict[str, Answer]:
    out = {}
    for k, v in d.items():
        kind = "choice" if k == "change_type" else "score" if k == "risk" else "noul"
        out[k] = Answer(kind, v[0], v[1], v[2] if len(v) > 2 else None)
    return out


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_cases(case: dict[str, Any]) -> None:
    v = verdict(_answers(case["d"]), case["files"], case["t"])
    assert (v.lane, v.uncertain) == (case["lane"], case["uncertain"])
    assert v.reasons or v.lane == "normal"


def test_clamp() -> None:
    assert (
        clamp_t(None) == DEFAULT_T
        and clamp_t(0.1) == 0.5
        and clamp_t(0.99) == 0.95
        and clamp_t(0.8) == 0.8
    )
