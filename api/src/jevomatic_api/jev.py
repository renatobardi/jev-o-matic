"""Cliente mínimo do jev (cópia enxuta de harness/client.py — o contexto de build é ./api).

Backend por env: JEV_BACKEND=openrouter|mock, modelo por JEV_MODEL. Os módulos acima só conhecem
`decide()` e `JevResult`."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

from .errors import TriageError

Question = dict[str, Any]


@dataclass(frozen=True)
class Answer:
    type: str
    value: Any  # noul: float 0–1 · choice: str · score: float
    confidence: float
    probabilities: dict[str, float] | None = None


@dataclass(frozen=True)
class JevResult:
    answers: dict[str, Answer]
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost: float | None
    model: str


def chance_normalized(probs: dict[str, float]) -> float:
    """(pmax − 1/n)/(1 − 1/n) — fórmula do confidence nativo, confirmada no lab 08."""
    n = len(probs)
    return (max(probs.values()) - 1 / n) / (1 - 1 / n) if n > 1 else 1.0


def normalize(ans: dict[str, Any]) -> Answer:
    t = ans.get("type", "unknown")
    probs = ans.get("probabilities")
    if t == "noul":
        p = float(ans["noul"])
        return Answer("noul", p, abs(p - 0.5) * 2)  # noul não traz confidence nativo
    if t in ("choice", "score"):
        conf = ans.get("confidence")
        if conf is None:
            conf = chance_normalized(probs) if probs else 0.0
        return Answer(t, ans[t], float(conf), probs)
    raise TriageError("jev_unavailable", f"Unexpected jev answer format ({t}).", 502)


def _mock(state: dict[str, Any], questions: dict[str, Question]) -> dict[str, Any]:
    """Determinístico e sem rede. Usa as categorias dos diffs pra dar respostas plausíveis."""
    cats = {d["category"] for d in state.get("diffs", [])}
    hints = {
        "touches_auth_security": "security",
        "touches_data_schema": "schema",
        "touches_infra_ci": "infra",
        "has_tests": "tests",
    }
    answers: dict[str, Any] = {}
    for key, q in questions.items():
        if q["type"] == "noul":
            answers[key] = {"type": "noul", "noul": 0.95 if hints.get(key) in cats else 0.05}
        elif q["type"] == "choice":
            opts = list(q["criteria"])
            pick = "docs" if cats == {"docs"} and "docs" in opts else opts[0]
            answers[key] = {
                "type": "choice",
                "choice": pick,
                "confidence": 0.9,
                "probabilities": {
                    o: (0.925 if o == pick else 0.075 / (len(opts) - 1)) for o in opts
                },
            }
        else:
            n = len(q["criteria"])
            lvl = 2 if cats & {"security", "schema"} else 0 if cats <= {"docs", "tests"} else 1
            answers[key] = {
                "type": "score",
                "score": float(lvl),
                "confidence": 0.9,
                "probabilities": {str(i): (0.94 if i == lvl else 0.06 / (n - 1)) for i in range(n)},
            }
    tokens = len(repr((state, questions))) // 3
    return {
        "answers": answers,
        "model": "mock/jev",
        "usage": {"input_tokens": tokens, "output_tokens": 0, "cost": 0.0},
    }


def _out_of_credits(e: Exception | None) -> bool:
    """OpenRouter: 402 = sem crédito na conta; 403 "Key limit exceeded" = limite da key."""
    if e is None:
        return False
    text = str(e).lower()
    return (
        getattr(e, "status_code", None) == 402
        or "limit exceeded" in text
        or "insufficient credits" in text
    )


def _call_openrouter(
    model: str, state: dict[str, Any], questions: dict[str, Question]
) -> dict[str, Any]:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise TriageError("jev_unavailable", "OPENROUTER_API_KEY is not set on the server.", 503)
    from openrouter import OpenRouter

    last: Exception | None = None
    for attempt in range(2):  # 1 retry
        try:
            with OpenRouter(api_key=key, x_open_router_title="jev-o-matic") as client:
                res = client.alpha.decisions.create(model=model, state=state, questions=questions)
            raw: dict[str, Any] = res.model_dump(mode="json")
            return raw
        except Exception as e:  # noqa: BLE001 — SDK alpha: qualquer falha vira erro único da API
            last = e
            time.sleep(0.5 * (attempt + 1))
    if _out_of_credits(last):
        raise TriageError(
            "credits_exhausted",
            "This demo ran out of credits. Thanks to everyone who tried it — the examples still work.",
            503,
        ) from last
    raise TriageError("jev_unavailable", "jev did not answer. Try again.", 502) from last


async def decide(state: dict[str, Any], questions: dict[str, Question]) -> JevResult:
    backend = os.getenv("JEV_BACKEND", "openrouter")
    model = os.getenv("JEV_MODEL", "typesafe/jev-1.13")
    t0 = time.perf_counter()
    if backend == "mock":
        raw = _mock(state, questions)
    elif backend == "openrouter":
        raw = await asyncio.to_thread(_call_openrouter, model, state, questions)
    else:
        raise TriageError("jev_unavailable", f"Unknown JEV_BACKEND: {backend}", 503)
    latency = (time.perf_counter() - t0) * 1000
    missing = set(questions) - set(raw["answers"])
    if missing:
        raise TriageError(
            "jev_unavailable", f"jev left questions unanswered: {sorted(missing)}", 502
        )
    usage = raw.get("usage", {})
    return JevResult(
        answers={k: normalize(raw["answers"][k]) for k in questions},
        latency_ms=round(latency, 1),
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        cost=usage.get("cost"),
        model=raw.get("model", model),
    )
