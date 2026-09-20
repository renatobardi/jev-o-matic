"""Cascata e guardas pelo pipeline inteiro: GitHub simulado, jev e LLM controlados por teste."""

from typing import Any

import httpx
import pytest

from jevomatic_api import triage as triage_mod
from jevomatic_api.errors import TriageError
from jevomatic_api.github import fetch_pr as real_fetch
from jevomatic_api.guards import DailyBudget, RateLimiter
from jevomatic_api.jev import Answer, JevResult
from jevomatic_api.llm import LlmAnswer, LlmResult, LlmUnavailable
from jevomatic_api.questions import QUESTIONS
from jevomatic_api.triage import Guards, triage

URL = "https://github.com/o/r/pull/1"
PR = {
    "title": "t",
    "body": "b",
    "user": {"login": "a"},
    "author_association": "NONE",
    "labels": [],
    "state": "open",
    "draft": False,
    "base": {"ref": "main"},
    "head": {"sha": "s"},
    "additions": 1,
    "deletions": 0,
    "changed_files": 1,
    "html_url": URL,
}
FILES = [
    {
        "filename": "src/werkzeug/security.py",
        "status": "modified",
        "additions": 1,
        "deletions": 0,
        "patch": '@@\n+    """docstring"""',
    }
]


def _jev(overrides: dict[str, Answer]) -> dict[str, Answer]:
    base = {k: Answer("noul", 0.02, 0.96) for k in QUESTIONS}
    base["change_type"] = Answer("choice", "docs", 0.9, {"docs": 0.92})
    base["risk"] = Answer("score", 0.05, 0.95, {"0": 0.97, "1": 0.03, "2": 0.0})
    return {**base, **overrides}


class Calls:
    def __init__(self) -> None:
        self.github = self.jev = self.llm = 0
        self.llm_questions: list[str] = []
        self.jev_answers: dict[str, Answer] = _jev(
            {"touches_auth_security": Answer("noul", 0.75, 0.5)}
        )
        self.llm_reply: dict[str, LlmAnswer] | None = {
            "touches_auth_security": LlmAnswer(Answer("noul", 0.0, 1.0), "só docstrings")
        }


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> Calls:
    calls = Calls()

    async def fake_fetch(ref: Any, client: Any = None) -> Any:
        calls.github += 1
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json=FILES if r.url.path.endswith("/files") else PR)
        )
        async with httpx.AsyncClient(transport=transport) as c:
            return await real_fetch(ref, c)

    async def fake_decide(state: Any, questions: Any) -> JevResult:
        calls.jev += 1
        return JevResult(calls.jev_answers, 400.0, 3000, 50, 0.0001, "jev-test")

    async def fake_llm(state: Any, questions: dict[str, Any]) -> LlmResult:
        calls.llm += 1
        calls.llm_questions = sorted(questions)
        if calls.llm_reply is None:
            raise LlmUnavailable("fora")
        return LlmResult(calls.llm_reply, 1500.0, 3200, 40, 0.002, "llm-test")

    monkeypatch.setattr(triage_mod, "fetch_pr", fake_fetch)
    monkeypatch.setattr(triage_mod, "decide", fake_decide)
    monkeypatch.setattr(triage_mod, "second_opinion", fake_llm)
    return calls


async def test_uncertain_flag_goes_to_llm_and_verdict_is_recomputed(wired: Calls) -> None:
    r = await triage(URL, guards=Guards())
    assert wired.llm == 1 and wired.llm_questions == ["touches_auth_security"]  # só a incerta
    d = r.decisions["touches_auth_security"]
    assert (d.source, d.value, d.confidence, d.rationale) == ("llm", 0.0, 1.0, "só docstrings")
    assert d.original is not None and (d.original.value, d.original.confidence) == (0.75, 0.5)
    assert r.decisions["risk"].source == "jev" and r.decisions["risk"].original is None
    assert (r.verdict.jev_lane, r.verdict.lane) == ("normal", "fast")  # LLM destravou a via rápida
    assert r.verdict.escalated == ["touches_auth_security"] and r.verdict.uncertain == []
    stage = r.trace[3]
    assert (stage.stage, stage.skipped, stage.latency_ms, stage.cost) == (
        "llm",
        False,
        1500.0,
        0.002,
    )
    assert r.versions.llm_model == "llm-test"


async def test_llm_can_also_raise_the_lane(wired: Calls) -> None:
    wired.llm_reply = {"touches_auth_security": LlmAnswer(Answer("noul", 1.0, 1.0), "muda o hash")}
    r = await triage(URL, guards=Guards())
    assert (r.verdict.jev_lane, r.verdict.lane) == ("normal", "senior")


async def test_nothing_uncertain_never_touches_llm(wired: Calls) -> None:
    wired.jev_answers = _jev({})
    r = await triage(URL, guards=Guards())
    assert wired.llm == 0 and r.verdict.lane == "fast" and r.verdict.escalated == []
    assert (
        r.trace[3].skipped
        and r.trace[3].note == "nenhuma decisão incerta"
        and r.versions.llm_model is None
    )


async def test_llm_down_keeps_jev_verdict_and_says_so(wired: Calls) -> None:
    wired.llm_reply = None
    r = await triage(URL, guards=Guards())
    assert r.verdict.lane == "normal" and r.verdict.uncertain == ["touches_auth_security"]
    assert r.trace[3].skipped and "indisponível" in (r.trace[3].note or "")
    assert r.decisions["touches_auth_security"].source == "jev"


async def test_llm_invalid_answer_is_ignored(wired: Calls) -> None:
    wired.llm_reply = {}
    r = await triage(URL, guards=Guards())
    assert r.verdict.lane == "normal" and r.verdict.escalated == []
    assert not r.trace[3].skipped and "válida" in (r.trace[3].note or "")


async def test_llm_budget_exhausted_disables_cascade_only(wired: Calls) -> None:
    g = Guards(budget=DailyBudget(max_llm_calls=0))
    r = await triage(URL, guards=g)
    assert wired.llm == 0 and wired.jev == 1 and "teto diário" in (r.trace[3].note or "")


async def test_spend_cap_blocks_new_triages(wired: Calls) -> None:
    g = Guards(budget=DailyBudget(max_spend_usd=0.001))
    await triage(URL, guards=g)  # gasta 0,0021
    with pytest.raises(TriageError) as e:
        await triage("https://github.com/o/r/pull/2", guards=g)
    assert (e.value.code, e.value.status) == ("budget_exhausted", 503)


async def test_cache_hit_costs_nothing_and_is_flagged(wired: Calls) -> None:
    g = Guards()
    first = await triage(URL, guards=g)
    second = await triage(URL + "/files", guards=g)  # mesma PR, URL escrita diferente
    assert (wired.github, wired.jev, wired.llm) == (1, 1, 1)
    assert not first.cached and second.cached and second.verdict == first.verdict
    await triage(URL, 0.9, guards=g)  # outro threshold = outra entrada
    assert wired.jev == 2


async def test_rate_limit_counts_misses_not_hits(wired: Calls) -> None:
    g = Guards(rate=RateLimiter(per_minute=2, per_day=100))
    await triage(URL, guards=g, client_ip="1.1.1.1")
    for _ in range(5):
        await triage(URL, guards=g, client_ip="1.1.1.1")  # cache: não conta
    await triage("https://github.com/o/r/pull/2", guards=g, client_ip="1.1.1.1")
    with pytest.raises(TriageError) as e:
        await triage("https://github.com/o/r/pull/3", guards=g, client_ip="1.1.1.1")
    assert e.value.status == 429 and wired.github == 2  # a 3ª nem foi ao GitHub
    await triage("https://github.com/o/r/pull/3", guards=g, client_ip="2.2.2.2")


async def test_one_round_covers_decisions_that_become_relevant(wired: Calls) -> None:
    # security incerto esconde um risk também incerto: com o flag frio, fast fica alcançável e o
    # risk passa a importar. A chamada única já leva os dois.
    wired.jev_answers = _jev(
        {
            "touches_auth_security": Answer("noul", 0.75, 0.5),
            "risk": Answer("score", 1.08, 0.66, {"0": 0.07, "1": 0.77, "2": 0.16}),
        }
    )
    wired.llm_reply = {
        "touches_auth_security": LlmAnswer(Answer("noul", 0.0, 1.0), "só docstrings"),
        "risk": LlmAnswer(Answer("score", 0.0, 1.0, {"0": 1.0}), "não altera runtime"),
    }
    r = await triage(URL, guards=Guards())
    assert wired.llm == 1 and wired.llm_questions == ["risk", "touches_auth_security"]
    assert r.verdict.lane == "fast" and r.verdict.uncertain == []
    assert r.verdict.escalated == ["risk", "touches_auth_security"]
