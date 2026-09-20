import pytest

from jevomatic_api.github import PrFile, PrRef, PullRequest
from jevomatic_api.state import (
    MAX_BODY_CHARS,
    MAX_PATCH_LINES,
    build_state,
    categorize,
    est_tokens,
    omit_reason,
    runtime_files,
    truncate_patch,
)


def F(
    path: str, patch: str | None = "@@ -1 +1 @@\n+x", add: int = 1, status: str = "modified"
) -> PrFile:
    return PrFile(path, status, add, 0, patch)


def PR(
    files: list[PrFile], body: str = "why", truncated: bool = False, total: int | None = None
) -> PullRequest:
    return PullRequest(
        PrRef("o", "r", 1),
        "t",
        body,
        "a",
        "MEMBER",
        ["bug"],
        "open",
        False,
        "main",
        "sha",
        10,
        2,
        total or len(files),
        "u",
        files,
        truncated,
    )


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("package-lock.json", "lockfile"),
        ("web/bun.lock", "lockfile"),
        ("api/uv.lock", "lockfile"),
        ("go.sum", "lockfile"),
        ("vendor/x/y.go", "vendored"),
        ("a/node_modules/z.js", "vendored"),
        ("dist/app.js", "build_output"),
        ("static/app.min.js", "minified"),
        ("app.js.map", "minified"),
        ("src/__snapshots__/a.snap", "snapshot"),
        ("api/v1/user.pb.go", "generated"),
        ("proto/user_pb2.py", "generated"),
        ("src/types.generated.ts", "generated"),
        ("logo.PNG", "binary"),
        ("fonts/a.woff2", "binary"),
    ],
)
def test_omit_patterns(path: str, reason: str) -> None:
    assert omit_reason(F(path)) == reason


def test_omit_no_patch_and_removed() -> None:
    assert omit_reason(F("src/big.py", patch=None)) == "no_patch"
    assert omit_reason(F("src/old.py", patch=None, status="removed")) == "removed"
    assert omit_reason(F("src/app.py")) is None
    assert omit_reason(F("src/builder.py")) is None  # "build" no nome não é diretório build/
    assert omit_reason(F("src/lock.py")) is None


@pytest.mark.parametrize(
    ("path", "cat"),
    [
        ("src/auth/login.py", "security"),
        ("lib/jwt_utils.ts", "security"),
        ("app/permissions.rb", "security"),
        ("tests/test_auth.py", "tests"),
        ("src/auth/login.test.ts", "tests"),
        ("pkg/auth/auth_test.go", "tests"),
        ("docs/security.md", "docs"),
        ("README.md", "docs"),
        ("db/migrations/0002_add_col.py", "schema"),
        ("schema.prisma", "schema"),
        ("sql/init.sql", "schema"),
        ("src/routes/users.ts", "api"),
        ("api/openapi.yaml", "api"),
        ("svc/user.proto", "api"),
        (".github/workflows/ci.yml", "infra"),
        ("Dockerfile", "infra"),
        ("infra/main.tf", "infra"),
        ("docker-compose.prod.yml", "infra"),
        ("src/utils/format.py", "source"),
        ("package.json", "deps"),
        ("web/package.json", "deps"),
        ("pyproject.toml", "deps"),
        ("requirements-dev.txt", "deps"),  # não é docs, apesar do .txt
        (".pre-commit-config.yaml", "deps"),
        ("go.mod", "deps"),
        ("src/package.json.ts", "source"),
    ],
)
def test_categorize(path: str, cat: str) -> None:
    assert categorize(path) == cat


def test_truncate_patch() -> None:
    p = "\n".join(f"+l{i}" for i in range(200))
    out, cut = truncate_patch(p, 120)
    assert cut and out.count("\n") == 120 and "truncado: +80 linhas" in out
    assert truncate_patch("+a\n+b", 120) == ("+a\n+b", False)


def test_priority_order_is_deterministic() -> None:
    files = [
        F("README.md"),
        F("src/z.py", add=5),
        F("src/a.py", add=5),
        F("src/big.py", add=50),
        F("tests/test_x.py"),
        F("Dockerfile"),
        F("src/routes/u.py"),
        F("db/migrations/1.sql"),
        F("src/auth/s.py"),
    ]
    got = [d["path"] for d in build_state(PR(files)).state["diffs"]]
    assert got == [
        "src/auth/s.py",
        "db/migrations/1.sql",
        "src/routes/u.py",
        "Dockerfile",
        "src/big.py",
        "src/a.py",
        "src/z.py",
        "tests/test_x.py",
        "README.md",
    ]
    assert got == [d["path"] for d in build_state(PR(list(reversed(files)))).state["diffs"]]


def test_budget_respected_and_reported() -> None:
    big = "\n".join("+" + "x" * 80 for _ in range(400))
    files = [F(f"src/m{i}.py", patch=big, add=400) for i in range(60)] + [
        F("src/auth/a.py", patch=big)
    ]
    b = build_state(PR(files), budget_tokens=5_000)
    assert b.sent.tokens_est <= 5_000 == b.sent.budget_tokens
    assert est_tokens(repr(b.state)) <= 5_000 + 50  # estimativa incremental ≈ estimativa do todo
    assert b.sent.files_included[0] == "src/auth/a.py"  # risco entra primeiro
    assert set(b.sent.files_truncated) <= set(b.sent.files_included)
    omitted = {o["path"]: o["reason"] for o in b.sent.files_omitted}
    assert omitted and set(omitted.values()) == {"budget"}
    assert len(b.sent.files_included) + len(omitted) == len(files)
    assert len(b.state["files_changed"]) == len(files)  # a lista de arquivos entra sempre


def test_report_fields() -> None:
    long = "\n".join(f"+l{i}" for i in range(MAX_PATCH_LINES + 10))
    files = [F("src/a.py", patch=long), F("uv.lock"), F("img.png", patch=None), F("src/b.py")]
    b = build_state(PR(files, body="x" * (MAX_BODY_CHARS + 1), truncated=True, total=350))
    assert b.sent.files_included == ["src/a.py", "src/b.py"] and b.sent.files_truncated == [
        "src/a.py"
    ]
    assert {"path": "uv.lock", "reason": "lockfile"} in b.sent.files_omitted
    assert {"path": "img.png", "reason": "binary"} in b.sent.files_omitted
    assert b.sent.files_omitted[-1] == {"path": "(+346 arquivos)", "reason": "github_file_cap"}
    assert b.sent.body_truncated and b.sent.file_list_truncated and b.sent.files_total == 350
    assert b.state["pull_request"]["description"].endswith("[descrição truncada]")
    assert b.categories["source"] == 2 and sum(b.categories.values()) == 2  # só revisáveis


def test_runtime_files_conta_so_codigo_de_producao() -> None:
    cats = {"security": 1, "schema": 0, "api": 2, "infra": 4, "source": 3, "deps": 5, "tests": 6}
    assert runtime_files(cats) == 6
    assert runtime_files({"docs": 3, "deps": 1, "tests": 2, "infra": 1}) == 0
