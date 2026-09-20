"""Proteções de uma app pública rodando com a key do dono. Tudo em memória, de propósito: sem
banco. Limitação aceita: reiniciar o processo zera contadores e cache — o teto duro é o limite
de crédito da própria key no OpenRouter."""

from __future__ import annotations

import os
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field

from .errors import TriageError

Clock = Callable[[], float]


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, "") or default)


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, "") or default)


@dataclass
class RateLimiter:
    """Janela deslizante por IP: N por minuto e M por dia."""

    per_minute: int = 6
    per_day: int = 60
    clock: Clock = time.time
    _hits: dict[str, deque[float]] = field(default_factory=dict)

    def check(self, ip: str) -> None:
        now = self.clock()
        hits = self._hits.setdefault(ip, deque())
        while hits and hits[0] <= now - 86_400:
            hits.popleft()
        if len(hits) >= self.per_day:
            raise TriageError(
                "rate_limited",
                "Limite diário de triagens atingido pra este IP.",
                429,
                retry_after=max(int(hits[0] + 86_400 - now), 1),
            )
        recent = [h for h in hits if h > now - 60]
        if len(recent) >= self.per_minute:
            raise TriageError(
                "rate_limited",
                "Muitas triagens em sequência. Espere um pouco.",
                429,
                retry_after=max(int(recent[0] + 60 - now), 1),
            )
        hits.append(now)
        if len(self._hits) > 10_000:  # não deixa o mapa crescer sem fim
            for stale in [k for k, v in self._hits.items() if not v or v[-1] <= now - 86_400]:
                del self._hits[stale]


@dataclass
class DailyBudget:
    """Teto diário de chamadas ao LLM e de gasto total. Vira à meia-noite UTC."""

    max_llm_calls: int = 200
    max_spend_usd: float = 1.0
    clock: Clock = time.time
    _day: int = -1
    llm_calls: int = 0
    spend: float = 0.0

    def _roll(self) -> None:
        day = int(self.clock() // 86_400)
        if day != self._day:
            self._day, self.llm_calls, self.spend = day, 0, 0.0

    def llm_allowed(self) -> bool:
        self._roll()
        return self.llm_calls < self.max_llm_calls and self.spend < self.max_spend_usd

    def jev_allowed(self) -> bool:
        self._roll()
        return self.spend < self.max_spend_usd

    def record(self, cost: float | None, llm: bool = False) -> None:
        self._roll()
        self.spend += cost or 0.0
        if llm:
            self.llm_calls += 1


@dataclass
class TtlCache[V]:
    ttl_s: float = 600.0
    max_entries: int = 256
    clock: Clock = time.time
    _data: OrderedDict[tuple[object, ...], tuple[float, V]] = field(default_factory=OrderedDict)

    def get(self, key: tuple[object, ...]) -> V | None:
        item = self._data.get(key)
        if item is None:
            return None
        if item[0] <= self.clock():
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return item[1]

    def put(self, key: tuple[object, ...], value: V) -> None:
        self._data[key] = (self.clock() + self.ttl_s, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)


def rate_limiter_from_env() -> RateLimiter:
    return RateLimiter(_env_int("RATE_PER_MIN", 6), _env_int("RATE_PER_DAY", 60))


def budget_from_env() -> DailyBudget:
    return DailyBudget(_env_int("MAX_LLM_CALLS_DAY", 200), _env_float("MAX_SPEND_DAY_USD", 1.0))
