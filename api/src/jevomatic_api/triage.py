"""O pipeline: URL → GitHub → state → jev → veredito. (LLM entra no M3.)"""

from __future__ import annotations

import time
from dataclasses import asdict

import httpx

from . import __version__
from .github import fetch_pr, parse_pr_url
from .jev import decide
from .questions import QUESTIONS, QUESTIONS_VERSION
from .schemas import (
    DecisionOut,
    PrOut,
    SentOut,
    StageOut,
    TriageResponse,
    VerdictOut,
    VersionsOut,
)
from .state import build_state, est_tokens
from .verdict import clamp_t, verdict

QUESTIONS_TOKENS = est_tokens(repr(QUESTIONS))


async def triage(
    url: str, t: float | None = None, client: httpx.AsyncClient | None = None
) -> TriageResponse:
    threshold = clamp_t(t)
    ref = parse_pr_url(url)

    t0 = time.perf_counter()
    pr = await fetch_pr(ref, client)
    built = build_state(pr)
    # o relatório mostra o total enviado: state + perguntas (smoke do M1: ~1,3k tokens fixos)
    built.sent.tokens_est += QUESTIONS_TOKENS
    github_ms = (time.perf_counter() - t0) * 1000

    res = await decide(built.state, QUESTIONS)

    t1 = time.perf_counter()
    v = verdict(res.answers, pr.changed_files, threshold)
    code_ms = (time.perf_counter() - t1) * 1000

    return TriageResponse(
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
        decisions={
            k: DecisionOut(
                type=a.type,
                value=a.value,
                confidence=round(a.confidence, 4),
                probabilities=a.probabilities,
            )
            for k, a in res.answers.items()
        },
        verdict=VerdictOut(**asdict(v)),
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
            StageOut(
                stage="llm", latency_ms=0, skipped=True, note="cascata ainda não implementada (M3)"
            ),
        ],
        versions=VersionsOut(questions=QUESTIONS_VERSION, jev_model=res.model, api=__version__),
        categories=built.categories,
    )
