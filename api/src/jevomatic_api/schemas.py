"""Contrato HTTP do POST /api/triage."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .verdict import T_MAX, T_MIN


class TriageRequest(BaseModel):
    url: str = Field(max_length=300)
    t: float | None = Field(default=None, ge=T_MIN, le=T_MAX)


class PrOut(BaseModel):
    slug: str
    title: str
    author: str
    author_association: str
    state: str
    draft: bool
    labels: list[str]
    additions: int
    deletions: int
    changed_files: int
    head_sha: str
    html_url: str


class JevOriginalOut(BaseModel):
    value: Any
    confidence: float
    probabilities: dict[str, float] | None = None


class DecisionOut(BaseModel):
    type: str
    value: Any
    confidence: float
    probabilities: dict[str, float] | None = None
    source: str = "jev"  # "jev" | "llm"
    rationale: str | None = None  # só quando source == "llm"; texto puro
    original: JevOriginalOut | None = None  # o que o jev tinha dito, quando o LLM respondeu


class VerdictOut(BaseModel):
    lane: str
    reasons: list[str]
    uncertain: list[str]  # ainda incertas depois da cascata
    t: float
    escalated: list[str] = []  # decisões que foram pro LLM
    jev_lane: str | None = None  # via que o jev sozinho daria (antes do LLM)


class OmittedOut(BaseModel):
    path: str
    reason: str


class SentOut(BaseModel):
    tokens_est: int
    budget_tokens: int
    files_total: int
    files_included: list[str]
    files_truncated: list[str]
    files_omitted: list[OmittedOut]
    body_truncated: bool
    file_list_truncated: bool


class StageOut(BaseModel):
    stage: str  # github | jev | code | llm
    latency_ms: float
    cost: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    skipped: bool = False
    note: str | None = None


class VersionsOut(BaseModel):
    questions: str
    jev_model: str
    llm_model: str | None = None
    api: str


class TriageResponse(BaseModel):
    pr: PrOut
    decisions: dict[str, DecisionOut]
    verdict: VerdictOut
    sent: SentOut
    trace: list[StageOut]
    versions: VersionsOut
    categories: dict[str, int]
    cached: bool = False


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    error: ErrorBody
