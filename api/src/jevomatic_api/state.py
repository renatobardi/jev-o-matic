"""PullRequest → `state` enviado ao jev, dentro de um orçamento de tokens.

O jev tem 32k de contexto (state + perguntas). O cabeçalho (título, descrição, lista de arquivos)
entra sempre; os patches entram por ordem de risco até o orçamento acabar. Tudo que fica de fora
é reportado — quem vê o veredito precisa saber sobre o que ele foi dado."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .github import PrFile, PullRequest

BUDGET_TOKENS = 20_000
MAX_BODY_CHARS = 4_000
MAX_PATCH_LINES = 120
MIN_PATCH_LINES = 30  # última tentativa de encaixar um arquivo antes de omitir
MAX_LISTED_FILES = 300

# Ordem em que os patches disputam o orçamento. Menor = entra primeiro.
CATEGORIES = ["security", "schema", "api", "infra", "source", "tests", "docs"]

_OMIT: list[tuple[str, re.Pattern[str]]] = [
    (
        "lockfile",
        re.compile(
            r"(^|/)(package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb?|uv\.lock|"
            r"poetry\.lock|Pipfile\.lock|Cargo\.lock|go\.sum|composer\.lock|Gemfile\.lock|flake\.lock)$"
        ),
    ),
    ("vendored", re.compile(r"(^|/)(node_modules|vendor|third_party|bower_components)/")),
    ("build_output", re.compile(r"(^|/)(dist|build|out|target|\.next|coverage)/")),
    ("minified", re.compile(r"\.min\.(js|css)$|\.map$")),
    ("snapshot", re.compile(r"(^|/)__snapshots__/|\.snap$")),
    (
        "generated",
        re.compile(
            r"\.pb\.go$|_pb2(_grpc)?\.py$|[._]generated\.|\.g\.dart$|(^|/)generated/|\.gen\.(go|ts)$"
        ),
    ),
    (
        "binary",
        re.compile(
            r"\.(png|jpe?g|gif|webp|ico|svg|pdf|zip|gz|tar|woff2?|ttf|eot|mp4|mov|wasm|jar|so|dylib|exe)$",
            re.IGNORECASE,
        ),
    ),
]

_TESTS = re.compile(
    r"(^|/)(tests?|__tests__|e2e|spec|specs|fixtures)/|(^|/)test_[^/]+$|"
    r"[._-](test|spec)\.[A-Za-z]+$|_test\.[A-Za-z]+$|(^|/)conftest\.py$"
)
_DOCS = re.compile(
    r"(^|/)docs?/|\.(md|mdx|rst|txt|adoc)$|(^|/)(LICENSE|NOTICE|CHANGELOG|AUTHORS)[^/]*$",
    re.IGNORECASE,
)
_SECURITY = re.compile(
    r"auth|secur|crypt|permission|rbac|(^|[/_.-])acl([/_.-]|$)|oauth|jwt|token|"
    r"passw|secret|session|login|signin|sso|saml|csrf|cors|sanitiz",
    re.IGNORECASE,
)
_SCHEMA = re.compile(
    r"(^|/)(migrations?|alembic|prisma|schema|schemas|ddl)/|migrat|\.sql$|"
    r"schema\.(rb|prisma|graphql|sql)$",
    re.IGNORECASE,
)
_API = re.compile(
    r"(^|/)(api|routes?|routers?|controllers?|handlers?|endpoints?|graphql|openapi)/|"
    r"\.proto$|openapi\.(ya?ml|json)$|swagger",
    re.IGNORECASE,
)
_INFRA = re.compile(
    r"(^|/)\.github/|(^|/)(Dockerfile|Containerfile|Caddyfile|Makefile|Jenkinsfile)[^/]*$|"
    r"docker-compose[^/]*\.ya?ml$|\.tf$|(^|/)(k8s|kubernetes|helm|charts|terraform|"
    r"ansible|deploy|infra|ci)/|nginx[^/]*\.conf$|\.gitlab-ci\.yml$",
    re.IGNORECASE,
)


def est_tokens(text: str) -> int:
    """Estimativa conservadora: diff tokeniza mais denso que prosa (~3 chars/token)."""
    return (len(text) + 2) // 3


def omit_reason(f: PrFile) -> str | None:
    for reason, pat in _OMIT:
        if pat.search(f.path):
            return reason
    if f.patch is None:
        return "removed" if f.status == "removed" else "no_patch"
    return None


def categorize(path: str) -> str:
    # tests/docs primeiro: `tests/test_auth.py` é teste, não lógica de autenticação.
    for name, pat in (
        ("tests", _TESTS),
        ("docs", _DOCS),
        ("security", _SECURITY),
        ("schema", _SCHEMA),
        ("api", _API),
        ("infra", _INFRA),
    ):
        if pat.search(path):
            return name
    return "source"


def truncate_patch(patch: str, max_lines: int) -> tuple[str, bool]:
    lines = patch.splitlines()
    if len(lines) <= max_lines:
        return patch, False
    return "\n".join(lines[:max_lines]) + f"\n… [truncado: +{len(lines) - max_lines} linhas]", True


@dataclass
class SentReport:
    tokens_est: int = 0
    budget_tokens: int = BUDGET_TOKENS
    files_total: int = 0
    files_included: list[str] = field(default_factory=list)
    files_truncated: list[str] = field(default_factory=list)
    files_omitted: list[dict[str, str]] = field(default_factory=list)
    body_truncated: bool = False
    file_list_truncated: bool = False


@dataclass
class BuiltState:
    state: dict[str, Any]
    sent: SentReport
    categories: dict[str, int]  # nº de arquivos revisáveis por categoria (pro veredito, em código)


def _entry(f: PrFile, cat: str, patch: str) -> dict[str, str]:
    return {"path": f.path, "category": cat, "status": f.status, "patch": patch}


def build_state(pr: PullRequest, budget_tokens: int = BUDGET_TOKENS) -> BuiltState:
    sent = SentReport(budget_tokens=budget_tokens, files_total=pr.changed_files)
    body = pr.body.strip()
    if len(body) > MAX_BODY_CHARS:
        body, sent.body_truncated = body[:MAX_BODY_CHARS] + "\n… [descrição truncada]", True

    cats = {f.path: categorize(f.path) for f in pr.files}
    listed = [
        f"{f.status} {f.path} (+{f.additions}/-{f.deletions}) [{cats[f.path]}]"
        for f in pr.files[:MAX_LISTED_FILES]
    ]
    sent.file_list_truncated = pr.files_truncated or len(pr.files) > MAX_LISTED_FILES

    state: dict[str, Any] = {
        "pull_request": {
            "repository": f"{pr.ref.owner}/{pr.ref.repo}",
            "title": pr.title,
            "description": body,
            "labels": pr.labels,
            "author_association": pr.author_association,
            "draft": pr.draft,
            "base_branch": pr.base_ref,
            "lines_added": pr.additions,
            "lines_deleted": pr.deletions,
            "files_changed_count": pr.changed_files,
        },
        "files_changed": listed,
        "diffs": [],
    }
    used = est_tokens(repr(state))

    candidates: list[PrFile] = []
    for f in pr.files:
        reason = omit_reason(f)
        if reason:
            sent.files_omitted.append({"path": f.path, "reason": reason})
        else:
            candidates.append(f)
    candidates.sort(
        key=lambda f: (CATEGORIES.index(cats[f.path]), -(f.additions + f.deletions), f.path)
    )

    for f in candidates:
        assert f.patch is not None
        for limit in (MAX_PATCH_LINES, MIN_PATCH_LINES):
            patch, cut = truncate_patch(f.patch, limit)
            cost = est_tokens(repr(_entry(f, cats[f.path], patch)))
            if used + cost <= budget_tokens:
                state["diffs"].append(_entry(f, cats[f.path], patch))
                used += cost
                sent.files_included.append(f.path)
                if cut:
                    sent.files_truncated.append(f.path)
                break
        else:
            sent.files_omitted.append({"path": f.path, "reason": "budget"})

    if pr.files_truncated:
        sent.files_omitted.append(
            {"path": f"(+{pr.changed_files - len(pr.files)} arquivos)", "reason": "github_file_cap"}
        )
    sent.tokens_est = used
    # só arquivos revisáveis: lockfile/binário/gerado não contam pro veredito
    counts = {c: sum(1 for f in candidates if cats[f.path] == c) for c in CATEGORIES}
    return BuiltState(state=state, sent=sent, categories=counts)
