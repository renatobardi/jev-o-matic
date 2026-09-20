"""Cliente único do lab. Backend plugável: hoje OpenRouter (Decisions API, alpha);
depois typesafe-sdk oficial. Os labs só conhecem JevClient/Decision."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


# --- perguntas (formato neutro, igual ao da Decisions API) -------------------
def noul(instructions: str, true: str | None = None, false: str | None = None) -> dict:
    q: dict[str, Any] = {"type": "noul", "instructions": instructions}
    if true or false:
        q["criteria"] = {"true": true or "", "false": false or ""}
    return q


def choice(instructions: str, criteria: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def score(instructions: str, criteria: list[str]) -> dict:
    return {"type": "score", "instructions": instructions, "criteria": criteria}


# --- resultado ---------------------------------------------------------------
@dataclass
class Decision:
    answers: dict[str, dict]  # por pergunta: type, value, confidence, probabilities
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost: float | None
    model: str
    backend: str
    raw: dict = field(repr=False, default_factory=dict)

    def value(self, key: str) -> Any:
        return self.answers[key]["value"]

    def confidence(self, key: str) -> float | None:
        return self.answers[key]["confidence"]


def _chance_normalized(probs: dict[str, float]) -> float:
    """(pmax - 1/n) / (1 - 1/n). Hipótese do lab 01: é assim que o jev calcula
    `confidence` (bate com score 3 níveis: pmax .65 → .47). Noul usa o mesmo com n=2."""
    n = len(probs)
    return (max(probs.values()) - 1 / n) / (1 - 1 / n) if n > 1 else 1.0


def _normalize(ans: dict) -> dict:
    t = ans.get("type")
    probs = ans.get("probabilities")
    if t == "noul":
        p = ans["noul"]
        # noul não traz confidence: deriva distância de 0.5 → [0,1]
        return {"type": t, "value": p, "confidence": abs(p - 0.5) * 2, "probabilities": None}
    if t == "choice":
        conf = ans.get("confidence")
        if conf is None and probs:
            conf = _chance_normalized(probs)
        return {"type": t, "value": ans["choice"], "confidence": conf, "probabilities": probs}
    if t == "score":
        conf = ans.get("confidence")
        if conf is None and probs:
            conf = _chance_normalized(probs)
        return {"type": t, "value": ans["score"], "confidence": conf, "probabilities": probs}
    return {"type": t or "unknown", "value": None, "confidence": None, "probabilities": None, "raw": ans}


def _mock(model: str, state: dict, questions: dict[str, dict]) -> dict:
    """Backend offline (JEV_BACKEND=mock): respostas determinísticas sem rede, só pra testar o harness."""
    time.sleep(0.01)
    answers: dict[str, dict] = {}
    for k, q in questions.items():
        if q["type"] == "noul":
            answers[k] = {"type": "noul", "noul": 0.5}
        elif q["type"] == "choice":
            opts = list(q["criteria"])
            probs = {o: round(1 / len(opts), 2) for o in opts}
            answers[k] = {"type": "choice", "choice": opts[0], "confidence": 0.0, "probabilities": probs}
        else:
            n = len(q["criteria"])
            probs = {str(i): round(1 / n, 2) for i in range(n)}
            answers[k] = {"type": "score", "score": (n - 1) / 2, "confidence": 0.0, "probabilities": probs}
    tokens = len(json.dumps([state, questions])) // 4
    return {"answers": answers, "model": f"mock/{model}", "usage": {"input_tokens": tokens, "output_tokens": 0, "cost": 0.0}}


class JevClient:
    def __init__(self, model: str | None = None, backend: str | None = None):
        self.backend = backend or os.getenv("JEV_BACKEND", "openrouter")
        self.model = model or os.getenv("JEV_MODEL", "typesafe/jev-1.13")
        if self.backend == "mock":
            self._or = None
            return
        if self.backend != "openrouter":
            raise NotImplementedError(f"backend '{self.backend}' ainda não implementado")
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise SystemExit("OPENROUTER_API_KEY ausente — copie .env.example para .env e preencha")
        from openrouter import OpenRouter

        self._or = OpenRouter(api_key=key, x_open_router_title="jev-o-matic")

    def decide(self, state: Any, questions: dict[str, dict]) -> Decision:
        if not isinstance(state, dict):
            state = {"input": state}
        t0 = time.perf_counter()
        if self.backend == "mock":
            raw = _mock(self.model, state, questions)
        else:
            res = self._or.alpha.decisions.create(model=self.model, state=state, questions=questions)
            raw = res.model_dump(mode="json")
        latency = (time.perf_counter() - t0) * 1000
        return Decision(
            answers={k: _normalize(v) for k, v in raw["answers"].items()},
            latency_ms=round(latency, 1),
            input_tokens=raw["usage"]["input_tokens"],
            output_tokens=raw["usage"]["output_tokens"],
            cost=raw["usage"].get("cost"),
            model=raw.get("model", self.model),
            backend=self.backend,
            raw=raw,
        )


# --- log de runs -------------------------------------------------------------
class RunLog:
    """Um JSONL por execução em results/<lab>/<timestamp>.jsonl"""

    def __init__(self, lab: str):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = ROOT / "results" / lab / f"{ts}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, item_id: str, decision: Decision, expected: dict | None = None, **extra):
        row = {"id": item_id, "expected": expected, **asdict(decision), **extra}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
