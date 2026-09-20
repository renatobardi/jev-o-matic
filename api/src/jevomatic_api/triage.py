"""O pipeline: URL → (cache) → GitHub → state → jev → veredito → LLM só na dúvida → veredito."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import httpx

from . import __version__
from .errors import TriageError
from .github import fetch_pr, parse_pr_url
from .guards import DailyBudget, RateLimiter, TtlCache
from .jev import Answer, decide
from .llm import LlmAnswer, LlmUnavailable, second_opinion
from .questions import QUESTIONS, QUESTIONS_VERSION
from .schemas import (
    DecisionOut,
    JevOriginalOut,
    PrOut,
    SentOut,
    StageOut,
    TriageResponse,
    VerdictOut,
    VersionsOut,
)
from .state import build_state, est_tokens, runtime_files
from .verdict import LANE_KEYS, clamp_t, verdict

QUESTIONS_TOKENS = est_tokens(repr(QUESTIONS))


@dataclass
class Guards:
    """Estado em memória do processo. Um por app; os testes criam o seu."""

    rate: RateLimiter = field(default_factory=RateLimiter)
    budget: DailyBudget = field(default_factory=DailyBudget)
    cache: TtlCache[TriageResponse] = field(default_factory=TtlCache)


def _decision(a: Answer, llm: LlmAnswer | None = None) -> DecisionOut:
    if llm is None:
        return DecisionOut(
            type=a.type,
            value=a.value,
            confidence=round(a.confidence, 4),
            probabilities=a.probabilities,
        )
    return DecisionOut(
        type=a.type,
        value=llm.answer.value,
        confidence=1.0,
        probabilities=None,
        source="llm",
        rationale=llm.rationale or None,
        original=JevOriginalOut(
            value=a.value, confidence=round(a.confidence, 4), probabilities=a.probabilities
        ),
    )


async def triage(
    url: str,
    t: float | None = None,
    *,
    guards: Guards | None = None,
    client_ip: str = "local",
    client: httpx.AsyncClient | None = None,
) -> TriageResponse:
    g = guards or Guards()
    threshold = clamp_t(t)
    ref = parse_pr_url(url)

    # Cache curto por PR (sem head sha na chave: acerto não custa nem uma ida ao GitHub).
    key = (ref.owner.lower(), ref.repo.lower(), ref.number, QUESTIONS_VERSION, round(threshold, 2))
    hit = g.cache.get(key)
    if hit is not None:
        return hit.model_copy(update={"cached": True})

    g.rate.check(client_ip)  # só o que custa conta pro limite
    if not g.budget.jev_allowed():
        raise TriageError(
            "budget_exhausted", "O teto de gasto de hoje foi atingido. Volte amanhã.", 503
        )

    t0 = time.perf_counter()
    pr = await fetch_pr(ref, client)
    built = build_state(pr)
    built.sent.tokens_est += QUESTIONS_TOKENS  # total enviado: state + perguntas
    github_ms = (time.perf_counter() - t0) * 1000

    res = await decide(built.state, QUESTIONS)
    g.budget.record(res.cost)

    t1 = time.perf_counter()
    runtime = runtime_files(built.categories)
    first = verdict(res.answers, pr.changed_files, threshold, runtime)
    code_ms = (time.perf_counter() - t1) * 1000

    final, answers = first, dict(res.answers)
    llm_answers: dict[str, LlmAnswer] = {}
    llm_stage = StageOut(stage="llm", latency_ms=0, skipped=True, note="nenhuma decisão incerta")
    llm_model: str | None = None
    if first.uncertain:
        if not g.budget.llm_allowed():
            llm_stage.note = "teto diário do LLM atingido — mantido o veredito do jev"
        else:
            try:
                # Uma chamada só: além do que está incerto AGORA, vai tudo que define a via e está
                # abaixo de t — responder um flag pode tornar relevante um risk que não era.
                ask = [k for k in LANE_KEYS if res.answers[k].confidence < threshold]
                op = await second_opinion(built.state, {k: QUESTIONS[k] for k in ask})
            except LlmUnavailable:
                llm_stage.note = "LLM indisponível — mantido o veredito do jev"
            else:
                g.budget.record(op.cost, llm=True)
                llm_answers, llm_model = op.answers, op.model
                answers.update({k: v.answer for k, v in llm_answers.items()})
                final = verdict(answers, pr.changed_files, threshold, runtime)
                llm_stage = StageOut(
                    stage="llm",
                    latency_ms=op.latency_ms,
                    cost=op.cost,
                    input_tokens=op.input_tokens,
                    output_tokens=op.output_tokens,
                    note=None if llm_answers else "o LLM não devolveu resposta válida",
                )

    out = TriageResponse(
        pr=PrOut(
            slug=ref.slug,
            title=pr.title,
            author=pr.author,
            author_association=pr.author_association,
            state=pr.state,
            draft=pr.draft,
            labels=pr.labels,
            additions=pr.additions,
            deletions=pr.deletions,
            changed_files=pr.changed_files,
            head_sha=pr.head_sha,
            html_url=pr.html_url,
        ),
        decisions={k: _decision(a, llm_answers.get(k)) for k, a in res.answers.items()},
        verdict=VerdictOut(**asdict(final), escalated=sorted(llm_answers), jev_lane=first.lane),
        sent=SentOut(**asdict(built.sent)),
        trace=[
            StageOut(stage="github", latency_ms=round(github_ms, 1)),
            StageOut(
                stage="jev",
                latency_ms=res.latency_ms,
                cost=res.cost,
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
            ),
            StageOut(stage="code", latency_ms=round(code_ms, 3)),
            llm_stage,
        ],
        versions=VersionsOut(
            questions=QUESTIONS_VERSION, jev_model=res.model, llm_model=llm_model, api=__version__
        ),
        categories=built.categories,
    )
    g.cache.put(key, out)
    return out
