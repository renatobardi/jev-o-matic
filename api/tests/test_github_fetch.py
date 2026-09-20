import time

import httpx
import pytest

from jevomatic_api.errors import TriageError
from jevomatic_api.github import MAX_FILES, PrRef, fetch_pr

REF = PrRef("o", "r", 1)
PR = {
    "title": "Fix login",
    "body": None,
    "user": {"login": "alice"},
    "author_association": "MEMBER",
    "labels": [{"name": "bug"}],
    "state": "open",
    "draft": False,
    "base": {"ref": "main"},
    "head": {"sha": "abc123"},
    "additions": 10,
    "deletions": 2,
    "changed_files": 2,
    "html_url": "https://github.com/o/r/pull/1",
}


def _file(i: int) -> dict[str, object]:
    return {
        "filename": f"src/f{i}.py",
        "status": "modified",
        "additions": 1,
        "deletions": 0,
        "patch": "@@ -1 +1 @@\n+x",
    }


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


async def test_success_and_hosts() -> None:
    seen: list[httpx.Request] = []

    def h(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path.endswith("/files"):
            return httpx.Response(200, json=[_file(1), {"filename": "img.png", "status": "added"}])
        return httpx.Response(200, json=PR)

    async with _client(httpx.MockTransport(h)) as c:
        pr = await fetch_pr(REF, c)
    assert {r.url.host for r in seen} == {"api.github.com"}
    assert pr.title == "Fix login" and pr.body == "" and pr.author == "alice"
    assert pr.labels == ["bug"] and pr.head_sha == "abc123" and not pr.files_truncated
    assert [f.path for f in pr.files] == ["src/f1.py", "img.png"]
    assert pr.files[1].patch is None and pr.files[1].additions == 0


async def test_pagination_and_cap() -> None:
    pages: list[str] = []

    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/files"):
            page = int(req.url.params["page"])
            pages.append(str(page))
            return httpx.Response(200, json=[_file(page * 1000 + i) for i in range(100)])
        return httpx.Response(200, json={**PR, "changed_files": 950})

    async with _client(httpx.MockTransport(h)) as c:
        pr = await fetch_pr(REF, c)
    assert pages == ["1", "2", "3"] and len(pr.files) == MAX_FILES and pr.files_truncated


async def test_token_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tkn")
    auth: list[str | None] = []

    def h(req: httpx.Request) -> httpx.Response:
        auth.append(req.headers.get("authorization"))
        return httpx.Response(200, json=[] if req.url.path.endswith("/files") else PR)

    async with _client(httpx.MockTransport(h)) as c:
        await fetch_pr(REF, c)
    assert auth == ["Bearer tkn", "Bearer tkn"]


@pytest.mark.parametrize(
    ("status", "headers", "code", "out"),
    [
        (404, {}, "pr_not_found", 404),
        (403, {}, "pr_not_found", 404),
        (
            403,
            {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(time.time()) + 120)},
            "github_rate_limited",
            429,
        ),
        (429, {"retry-after": "30"}, "github_rate_limited", 429),
        (500, {}, "github_unavailable", 502),
    ],
)
async def test_errors(status: int, headers: dict[str, str], code: str, out: int) -> None:
    async with _client(httpx.MockTransport(lambda r: httpx.Response(status, headers=headers))) as c:
        with pytest.raises(TriageError) as e:
            await fetch_pr(REF, c)
    assert (e.value.code, e.value.status) == (code, out)
    if out == 429:
        assert e.value.retry_after and e.value.retry_after > 0


async def test_network_failure() -> None:
    def h(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    async with _client(httpx.MockTransport(h)) as c:
        with pytest.raises(TriageError) as e:
            await fetch_pr(REF, c)
    assert e.value.status == 502
