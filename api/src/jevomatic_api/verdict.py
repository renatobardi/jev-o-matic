"""Veredito determinístico: decisões do jev → lane de revisão.

Regra pequena de propósito (lab 04: compor muitos átomos faz OR dos falsos positivos).
Uma decisão só DECIDE a lane se tiver confidence ≥ t; abaixo disso ela entra em `uncertain`
(gatilho da cascata pro LLM) e a lane cai no lado seguro:
  senior  ← flag de risco positivo e confiante, ou risk nível 2 confiante
  fast    ← tipo de baixo risco confiante + TODOS os flags negativos e confiantes + risk 0 confiante + PR pequeno
  normal  ← todo o resto
A mesma tabela de casos (tests/verdict_cases.json) valida o port em TypeScript do web."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

DEFAULT_T = 0.7  # lab 05: cascata em 0,7 igualou o LLM puro
T_MIN, T_MAX = 0.5, 0.95
FLAGS = ["touches_auth_security", "touches_data_schema", "breaking_api"]
FAST_TYPES = {"docs", "tests_only", "deps"}
FAST_MAX_FILES = 25
FAST_RUNNER_UP = 0.3  # tipo "quase fast": vale perguntar ao LLM


class AnswerLike(Protocol):
    @property
    def value(self) -> Any: ...
    @property
    def confidence(self) -> float: ...
    @property
    def probabilities(self) -> dict[str, float] | None: ...


@dataclass
class Verdict:
    lane: str
    reasons: list[str] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)
    t: float = DEFAULT_T


def clamp_t(t: float | None) -> float:
    return DEFAULT_T if t is None else min(max(t, T_MIN), T_MAX)


def verdict(
    decisions: Mapping[str, AnswerLike], files_changed: int, t: float = DEFAULT_T
) -> Verdict:
    v = Verdict(lane="normal", t=t)
    risk, ctype = decisions["risk"], decisions["change_type"]
    sure = {k: decisions[k].confidence >= t for k in [*FLAGS, "risk", "change_type"]}

    v.uncertain = [k for k in [*FLAGS, "risk"] if not sure[k]]
    probs = ctype.probabilities or {}
    near_fast = ctype.value in FAST_TYPES or any(
        probs.get(o, 0) >= FAST_RUNNER_UP for o in FAST_TYPES
    )
    if not sure["change_type"] and near_fast:
        v.uncertain.append("change_type")

    hot = [k for k in FLAGS if sure[k] and decisions[k].value >= 0.5]
    if hot or (sure["risk"] and round(risk.value) == 2):
        v.lane = "senior"
        v.reasons = [*hot, *(["risk_severe"] if sure["risk"] and round(risk.value) == 2 else [])]
        return v

    all_cold = all(sure[k] and decisions[k].value < 0.5 for k in FLAGS)
    if (
        sure["change_type"]
        and ctype.value in FAST_TYPES
        and all_cold
        and sure["risk"]
        and round(risk.value) == 0
        and files_changed <= FAST_MAX_FILES
    ):
        v.lane = "fast"
        v.reasons = [f"type_{ctype.value}", "no_risk_flags", "risk_none", "small"]
        return v

    if ctype.value in FAST_TYPES and files_changed > FAST_MAX_FILES:
        v.reasons.append("too_many_files_for_fast")
    if v.uncertain:
        v.reasons.append("uncertain_decisions")
    return v
