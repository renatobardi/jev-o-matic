import pytest

from jevomatic_api import jev
from jevomatic_api.errors import TriageError
from jevomatic_api.questions import QUESTIONS, QUESTIONS_VERSION


def test_normalize_noul_derives_confidence() -> None:
    a = jev.normalize({"type": "noul", "noul": 0.97})
    assert (a.type, a.value, round(a.confidence, 2), a.probabilities) == ("noul", 0.97, 0.94, None)
    assert jev.normalize({"type": "noul", "noul": 0.5}).confidence == 0.0


def test_normalize_choice_and_score() -> None:
    c = jev.normalize(
        {
            "type": "choice",
            "choice": "docs",
            "confidence": 0.8,
            "probabilities": {"docs": 0.9, "deps": 0.1},
        }
    )
    assert (c.value, c.confidence) == ("docs", 0.8)
    s = jev.normalize(
        {"type": "score", "score": 1.35, "probabilities": {"0": 0.0, "1": 0.65, "2": 0.35}}
    )
    assert s.value == 1.35 and round(s.confidence, 3) == 0.475  # fórmula do lab 08


def test_normalize_unknown_type() -> None:
    with pytest.raises(TriageError):
        jev.normalize({"type": "UNKNOWN", "raw": {}})


async def test_mock_backend_answers_every_question(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEV_BACKEND", "mock")
    state = {"diffs": [{"category": "security", "path": "src/auth.py", "patch": "+x"}]}
    r = await jev.decide(state, QUESTIONS)
    assert set(r.answers) == set(QUESTIONS) and r.model == "mock/jev" and r.latency_ms >= 0
    assert r.answers["touches_auth_security"].value == 0.95 and r.answers["has_tests"].value == 0.05
    assert r.answers["risk"].value == 2.0
    docs = await jev.decide({"diffs": [{"category": "docs"}]}, QUESTIONS)
    assert docs.answers["change_type"].value == "docs" and docs.answers["risk"].value == 0.0


async def test_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEV_BACKEND", "nope")
    with pytest.raises(TriageError) as e:
        await jev.decide({}, QUESTIONS)
    assert e.value.status == 503


async def test_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEV_BACKEND", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(TriageError) as e:
        await jev.decide({}, QUESTIONS)
    assert e.value.status == 503


def test_questions_shape() -> None:
    assert QUESTIONS_VERSION
    for key, q in QUESTIONS.items():
        assert q["type"] in ("noul", "choice", "score") and q["instructions"], key
        if q["type"] == "noul":
            assert set(q["criteria"]) == {"true", "false"}
        if q["type"] == "score":
            assert 2 <= len(q["criteria"]) <= 10
        if q["type"] == "choice":
            assert 2 <= len(q["criteria"]) <= 255
