"""URL de PR → dados do PR via GitHub REST.

A URL do usuário nunca é buscada: dela só saem owner/repo/number, validados, e todo request
vai pra `api.github.com` (sem SSRF)."""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from .errors import TriageError

API = "https://api.github.com"
MAX_FILES = 300
PER_PAGE = 100
TIMEOUT = 10.0

# Regras de nome do GitHub: owner alfanumérico com hífen interno (≤39); repo com . _ - (≤100).
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
_REPO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_NUMBER = re.compile(r"^[1-9][0-9]{0,8}$")


@dataclass(frozen=True)
class PrRef:
    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


@dataclass(frozen=True)
class PrFile:
    path: str
    status: str
    additions: int
    deletions: int
    patch: str | None  # None: binário ou grande demais pro GitHub devolver


@dataclass(frozen=True)
class PullRequest:
    ref: PrRef
    title: str
    body: str
    author: str
    author_association: str
    labels: list[str]
    state: str
    draft: bool
    base_ref: str
    head_sha: str
    additions: int
    deletions: int
    changed_files: int
    html_url: str
    files: list[PrFile] = field(default_factory=list)
    files_truncated: bool = False  # PR tem mais arquivos que MAX_FILES


def parse_pr_url(url: str) -> PrRef:
    bad = TriageError(
        "invalid_url",
        "Paste the URL of a public pull request: https://github.com/owner/repo/pull/123",
        422,
    )
    if len(url) > 300:
        raise bad
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or parts.netloc.lower() not in ("github.com", "www.github.com"):
        raise bad
    seg = [s for s in parts.path.split("/") if s]
    if len(seg) < 4 or seg[2] != "pull":
        raise bad
    owner, repo, number = seg[0], seg[1], seg[3]
    if not (_OWNER.match(owner) and _REPO.match(repo) and _NUMBER.match(number)) or repo in (
        ".",
        "..",
    ):
        raise bad
    return PrRef(owner, repo, int(number))


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "jev-o-matic",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _check(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    if r.status_code in (403, 429) and (
        r.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in r.headers
    ):
        reset = int(r.headers.get("x-ratelimit-reset", "0") or 0)
        wait = int(r.headers.get("retry-after", "0") or 0) or max(reset - int(time.time()), 1)
        raise TriageError(
            "github_rate_limited",
            "GitHub API rate limit reached. Try again later.",
            429,
            retry_after=wait,
        )
    if r.status_code in (401, 403, 404):
        raise TriageError("pr_not_found", "Pull request not found, or it is private.", 404)
    raise TriageError("github_unavailable", f"GitHub answered {r.status_code}.", 502)


def _require_public(pr: dict[str, Any]) -> None:
    """Defesa em profundidade: o GITHUB_TOKEN deve ser só-leitura de repo público, mas se um dia
    alguém gravar um token com acesso a repo privado, esta demo (aberta, sem login, que manda o
    diff pra terceiros) viraria um leitor público dos repos privados do dono. Recusa aqui, com a
    MESMA resposta de "não encontrado" — não confirma que o repo existe."""
    repo = (pr.get("base") or {}).get("repo") or {}
    if repo.get("private") is not False or repo.get("visibility", "public") != "public":
        raise TriageError("pr_not_found", "Pull request not found, or it is private.", 404)


async def fetch_pr(ref: PrRef, client: httpx.AsyncClient | None = None) -> PullRequest:
    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT)
    base = f"{API}/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}"
    try:
        # PR e 1ª página de arquivos em paralelo: em sequência o GitHub custava mais que o jev
        r, first = await asyncio.gather(
            client.get(base, headers=_headers()),
            client.get(
                f"{base}/files", params={"per_page": PER_PAGE, "page": 1}, headers=_headers()
            ),
        )
        _check(r)
        d = r.json()
        _require_public(d)
        files: list[PrFile] = []
        page, fr = 1, first
        while True:
            _check(fr)
            batch = fr.json()
            files += [
                PrFile(
                    f["filename"],
                    f.get("status", "modified"),
                    f.get("additions", 0),
                    f.get("deletions", 0),
                    f.get("patch"),
                )
                for f in batch
            ]
            if len(batch) < PER_PAGE or len(files) >= MAX_FILES:
                break
            page += 1
            fr = await client.get(
                f"{base}/files", params={"per_page": PER_PAGE, "page": page}, headers=_headers()
            )
    except httpx.HTTPError as e:
        raise TriageError("github_unavailable", "Could not reach GitHub.", 502) from e
    finally:
        if own:
            await client.aclose()

    total = int(d.get("changed_files", len(files)))
    return PullRequest(
        ref=ref,
        title=d.get("title") or "",
        body=d.get("body") or "",
        author=(d.get("user") or {}).get("login", ""),
        author_association=d.get("author_association", "NONE"),
        labels=[lb["name"] for lb in d.get("labels", [])],
        state=d.get("state", ""),
        draft=bool(d.get("draft")),
        base_ref=(d.get("base") or {}).get("ref", ""),
        head_sha=(d.get("head") or {}).get("sha", ""),
        additions=int(d.get("additions", 0)),
        deletions=int(d.get("deletions", 0)),
        changed_files=total,
        # montado aqui, não copiado da resposta: o link que a página abre é sempre github.com
        html_url=f"https://github.com/{ref.owner}/{ref.repo}/pull/{ref.number}",
        files=files[:MAX_FILES],
        files_truncated=total > MAX_FILES,
    )
