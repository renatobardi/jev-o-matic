from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from jevomatic_api import main as main_mod
from jevomatic_api import triage as triage_mod
from jevomatic_api.github import fetch_pr as real_fetch
from jevomatic_api.main import app
from jevomatic_api.questions import QUESTIONS, QUESTIONS_VERSION
from jevomatic_api.triage import Guards

PR = {
    "title": "Harden token check",
    "body": "Fixes #9: tokens were compared with ==",
    "user": {"login": "alice"},
    "author_association": "MEMBER",
    "labels": [],
    "state": "open",
    "draft": False,
    "base": {"ref": "main"},
    "head": {"sha": "deadbeef"},
    "additions": 12,
    "deletions": 3,
    "changed_files": 3,
    "html_url": "https://github.com/o/r/pull/1",
}
FILES = [
    {
        "filename": "src/auth/token.py",
        "status": "modified",
        "additions": 8,
        "deletions": 3,
        "patch": "@@\n+hmac.compare_digest(a, b)",
    },
    {
        "filename": "tests/test_token.py",
        "status": "added",
        "additions": 4,
        "deletions": 0,
        "patch": "@@\n+def test_x(): ...",
    },
    {
        "filename": "uv.lock",
        "status": "modified",
        "additions": 0,
        "deletions": 0,
        "patch": "@@\n+x",
    },
]


def _gh(
    files: list[dict[str, Any]], pr: dict[str, Any] = PR, status: int = 200
) -> httpx.MockTransport:
    def h(req: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json=files if req.url.path.endswith("/files") else pr)

    return httpx.MockTransport(h)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("JEV_BACKEND", "mock")
    # guardas novas por teste: cache e rate limit são estado do processo
    monkeypatch.setattr(main_mod, "GUARDS", Guards())
    return TestClient(app)


def _patch_github(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    async def fake(ref: Any, client: Any = None) -> Any:
        async with httpx.AsyncClient(transport=transport) as c:
            return await real_fetch(ref, c)

    monkeypatch.setattr(triage_mod, "fetch_pr", fake)


def test_full_schema_security_pr(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_github(monkeypatch, _gh(FILES))
    r = api.post("/api/triage", json={"url": "https://github.com/o/r/pull/1"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["pr"]["slug"] == "o/r#1" and d["pr"]["head_sha"] == "deadbeef"
    assert set(d["decisions"]) == set(QUESTIONS)
    assert all({"type", "value", "confidence", "source"} <= set(x) for x in d["decisions"].values())
    assert d["verdict"]["lane"] == "senior" and "touches_auth_security" in d["verdict"]["reasons"]
    assert d["verdict"]["t"] == 0.7 and d["verdict"]["uncertain"] == []
    assert d["sent"]["files_included"] == ["src/auth/token.py", "tests/test_token.py"]
    assert d["sent"]["files_omitted"] == [{"path": "uv.lock", "reason": "lockfile"}]
    assert [s["stage"] for s in d["trace"]] == ["github", "jev", "code", "llm"] and d["trace"][3][
        "skipped"
    ]
    assert d["versions"]["questions"] == QUESTIONS_VERSION and d["cached"] is False
    assert d["categories"]["security"] == 1 and d["categories"]["tests"] == 1


def test_docs_pr_is_fast_and_t_is_echoed(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    files = [
        {
            "filename": "docs/guide.md",
            "status": "modified",
            "additions": 3,
            "deletions": 1,
            "patch": "@@\n+typo",
        }
    ]
    _patch_github(monkeypatch, _gh(files, {**PR, "changed_files": 1}))
    d = api.post("/api/triage", json={"url": "https://github.com/o/r/pull/1", "t": 0.8}).json()
    assert d["verdict"]["lane"] == "fast" and d["verdict"]["t"] == 0.8


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        ({"url": "https://gitlab.com/o/r/pull/1"}, 422, "invalid_url"),
        ({}, 422, "invalid_request"),
        ({"url": "https://github.com/o/r/pull/1", "t": 0.2}, 422, "invalid_request"),
        ({"url": "x" * 400}, 422, "invalid_request"),
    ],
)
def test_bad_requests(api: TestClient, payload: dict[str, Any], status: int, code: str) -> None:
    r = api.post("/api/triage", json=payload)
    assert (r.status_code, r.json()["error"]["code"]) == (status, code)


def test_github_errors_are_mapped(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_github(monkeypatch, _gh([], status=404))
    r = api.post("/api/triage", json={"url": "https://github.com/o/r/pull/1"})
    assert (r.status_code, r.json()["error"]["code"]) == (404, "pr_not_found")


def test_jev_down_is_502_or_503(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_github(monkeypatch, _gh(FILES))
    monkeypatch.setenv("JEV_BACKEND", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = api.post("/api/triage", json={"url": "https://github.com/o/r/pull/1"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "jev_unavailable"
