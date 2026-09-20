import pytest

from jevomatic_api.errors import TriageError
from jevomatic_api.guards import DailyBudget, RateLimiter, TtlCache


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_rate_per_minute_and_reset() -> None:
    c = Clock()
    r = RateLimiter(per_minute=2, per_day=100, clock=c)
    r.check("a")
    r.check("a")
    with pytest.raises(TriageError) as e:
        r.check("a")
    assert (
        e.value.status == 429
        and e.value.code == "rate_limited"
        and 1 <= (e.value.retry_after or 0) <= 60
    )
    r.check("b")  # outro IP não é afetado
    c.now += 61
    r.check("a")


def test_rate_per_day() -> None:
    c = Clock()
    r = RateLimiter(per_minute=100, per_day=3, clock=c)
    for _ in range(3):
        r.check("a")
        c.now += 120
    with pytest.raises(TriageError) as e:
        r.check("a")
    assert (e.value.retry_after or 0) > 3600
    c.now += 86_400
    r.check("a")


def test_rejected_request_does_not_count() -> None:
    c = Clock()
    r = RateLimiter(per_minute=1, per_day=100, clock=c)
    r.check("a")
    for _ in range(5):
        with pytest.raises(TriageError):
            r.check("a")
    c.now += 61
    r.check("a")  # as 5 recusas não estenderam a janela


def test_budget_caps_and_midnight_rollover() -> None:
    c = Clock(now=86_400 * 100 + 10)
    b = DailyBudget(max_llm_calls=2, max_spend_usd=0.01, clock=c)
    assert b.llm_allowed() and b.jev_allowed()
    b.record(0.001, llm=True)
    b.record(0.001, llm=True)
    assert not b.llm_allowed() and b.jev_allowed()  # chamadas estouraram; gasto ainda não
    b.record(0.02)
    assert not b.jev_allowed()
    c.now += 86_400
    assert b.llm_allowed() and b.jev_allowed() and b.spend == 0.0 and b.llm_calls == 0


def test_budget_none_cost() -> None:
    b = DailyBudget()
    b.record(None, llm=True)
    assert b.spend == 0.0 and b.llm_calls == 1


def test_cache_ttl_and_lru() -> None:
    c = Clock()
    cache: TtlCache[str] = TtlCache(ttl_s=10, max_entries=2, clock=c)
    cache.put(("a",), "A")
    cache.put(("b",), "B")
    assert cache.get(("a",)) == "A"  # toca "a": "b" vira o mais antigo
    cache.put(("c",), "C")
    assert cache.get(("b",)) is None and cache.get(("a",)) == "A" and cache.get(("c",)) == "C"
    c.now += 11
    assert cache.get(("a",)) is None
