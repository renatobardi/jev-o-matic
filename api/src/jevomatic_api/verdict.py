"""Veredito determinístico: decisões do jev → lane de revisão.

Regra pequena de propósito (lab 04: compor muitos átomos faz OR dos falsos positivos).
Uma decisão só DECIDE a lane se tiver confidence ≥ t. Abaixo disso a lane cai no lado seguro e a
decisão entra em `uncertain` (gatilho da cascata pro LLM) — mas só se ainda puder mudar a lane:
  senior  ← flag de risco positivo e confiante, ou risk nível 2 confiante
  fast    ← tipo de baixo risco confiante + TODOS os flags negativos e confiantes + risk 0 confiante + PR pequeno
            + NENHUM arquivo de código de produção (contado em código pelo state.py, não pelo jev)
  normal  ← todo o resto
A mesma tabela de casos (tests/verdict_cases.json) valida o port em TypeScript do web."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

DEFAULT_T = 0.7  # lab 05: cascata em 0,7 igualou o LLM puro
T_MIN, T_MAX = 0.5, 0.95
FLAGS = ["touches_auth_security", "touches_data_schema", "breaking_api"]
LANE_KEYS = [*FLAGS, "risk", "change_type"]  # tudo que pode definir a via
FAST_TYPES = {"docs", "tests_only", "deps"}
FAST_MAX_FILES = 25
FAST_RUNNER_UP = 0.3  # tipo "quase fast": vale perguntar ao LLM
SEVERE_MIN_PROB = 0.3  # risk incerto só importa se o nível 2 é plausível


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
    decisions: Mapping[str, AnswerLike],
    files_changed: int,
    t: float = DEFAULT_T,
    runtime_files: int = 0,
) -> Verdict:
    v = Verdict(lane="normal", t=t)
    risk, ctype = decisions["risk"], decisions["change_type"]
    sure = {k: decisions[k].confidence >= t for k in [*FLAGS, "risk", "change_type"]}
    risk_severe = sure["risk"] and round(risk.value) == 2

    hot = [k for k in FLAGS if sure[k] and decisions[k].value >= 0.5]
    if hot or risk_severe:
        # senior é o teto: nenhuma decisão incerta muda a lane, então não há o que escalar
        v.lane = "senior"
        v.reasons = [*hot, *(["risk_severe"] if risk_severe else [])]
        return v

    # `uncertain` = só o que ainda pode mudar a lane (smoke do M1: escalar por todo score
    # incerto mandava 6 de 7 PRs pro LLM; score é o primitivo menos confiável — labs 03/04)
    all_cold = all(sure[k] and decisions[k].value < 0.5 for k in FLAGS)
    small = files_changed <= FAST_MAX_FILES
    probs = ctype.probabilities or {}
    near_fast = ctype.value in FAST_TYPES or any(
        probs.get(o, 0) >= FAST_RUNNER_UP for o in FAST_TYPES
    )
    no_runtime = runtime_files == 0  # guarda em código: jev diz "docs", diff tem lógica → sem fast
    fast_reachable = all_cold and small and near_fast and no_runtime

    v.uncertain = [k for k in FLAGS if not sure[k]]  # flag incerto pode virar senior
    if not sure["risk"]:
        could_be_severe = (risk.probabilities or {}).get("2", 0.0) >= SEVERE_MIN_PROB
        if could_be_severe or fast_reachable:
            v.uncertain.append("risk")
    if not sure["change_type"] and fast_reachable:
        v.uncertain.append("change_type")

    if (
        sure["change_type"]
        and ctype.value in FAST_TYPES
        and all_cold
        and small
        and no_runtime
        and sure["risk"]
        and round(risk.value) == 0
    ):
        v.lane = "fast"
        v.reasons = [
            f"type_{ctype.value}",
            "no_risk_flags",
            "risk_none",
            "small",
            "no_runtime_files",
        ]
        return v

    if ctype.value in FAST_TYPES and not small:
        v.reasons.append("too_many_files_for_fast")
    if ctype.value in FAST_TYPES and not no_runtime:
        v.reasons.append("runtime_files_block_fast")
    if v.uncertain:
        v.reasons.append("uncertain_decisions")
    return v
