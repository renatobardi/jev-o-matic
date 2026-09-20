import pytest

from jevomatic_api.errors import TriageError
from jevomatic_api.github import PrRef, parse_pr_url


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/fastapi/fastapi/pull/123",
        "https://github.com/fastapi/fastapi/pull/123/",
        "https://github.com/fastapi/fastapi/pull/123/files",
        "https://github.com/fastapi/fastapi/pull/123/files?diff=split#diff-abc",
        "https://www.github.com/fastapi/fastapi/pull/123",
        "  https://github.com/fastapi/fastapi/pull/123  ",
    ],
)
def test_valid(url: str) -> None:
    assert parse_pr_url(url) == PrRef("fastapi", "fastapi", 123)


def test_repo_with_dots_and_dashes() -> None:
    assert parse_pr_url("https://github.com/a-b/my.repo_x-1/pull/7") == PrRef(
        "a-b", "my.repo_x-1", 7
    )


@pytest.mark.parametrize(
    "url",
    [
        "",
        "github.com/o/r/pull/1",
        "http://github.com/o/r/pull/1",
        "https://gitlab.com/o/r/pull/1",
        "https://github.com.evil.io/o/r/pull/1",
        "https://evil.io/github.com/o/r/pull/1",
        "https://github.com@evil.io/o/r/pull/1",
        "https://github.com/o/r/issues/1",
        "https://github.com/o/r/pull/",
        "https://github.com/o/r/pull/abc",
        "https://github.com/o/r/pull/0",
        "https://github.com/o/r/pull/-1",
        "https://github.com/o/r/pull/1e3",
        "https://github.com/-bad/r/pull/1",
        "https://github.com/bad-/r/pull/1",
        "https://github.com/o/../pull/1",
        "https://github.com/o/r%2F..%2Fx/pull/1",
        "https://github.com/o/r/pull/1" + "x" * 300,
    ],
)
def test_invalid(url: str) -> None:
    with pytest.raises(TriageError) as e:
        parse_pr_url(url)
    assert e.value.status == 422 and e.value.code == "invalid_url"
