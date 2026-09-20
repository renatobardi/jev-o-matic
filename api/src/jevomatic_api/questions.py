"""Perguntas de triagem de PR. Mudou o wording → bump em QUESTIONS_VERSION (invalida cache e
muda o que a demo mede — lab 00 v3: o wording define o conceito).

Regras dos labs aplicadas:
- escopo explícito: "the diff adds/removes/modifies …", nunca "mentions" (lab 06: genérico casa palavra-chave)
- `criteria` true/false com os quase-positivos conhecidos no false (lab 06 v3)
- relação dentro de UMA pergunta; nada de átomos pra compor depois (labs 04 e 06 v4)
- score com níveis mutuamente exclusivos, ancorados em estado observável (lab 04 u1)
- contagem e tamanho ficam em código, não aqui

pr-v2 (#12, decisões no doc 14 do Project):
- `risk` deixou de ser contrafactual ("quanto dano um erro causaria") e passou a descrever o que o
  diff TOCA — no smoke do v1 ficou incerto em 6 de 7 PRs
- nível 2 do `risk` cobre também o que nenhum flag cobre: dinheiro, concorrência/estado, deleção
- `change_type` ganhou `mixed`: PR misto não cabia em opções "Only …" e a confidence caía por
  artefato do enum. `mixed` nunca é via rápida (não está em FAST_TYPES)
- `breaking_api` só vale com marca de público VISÍVEL no diff; sem marca → false (subestima, não chuta)
"""

from __future__ import annotations

from typing import Any

QUESTIONS_VERSION = "pr-v2"

Question = dict[str, Any]


def _noul(instructions: str, true: str, false: str) -> Question:
    return {
        "type": "noul",
        "instructions": instructions,
        "criteria": {"true": true, "false": false},
    }


QUESTIONS: dict[str, Question] = {
    "change_type": {
        "type": "choice",
        "instructions": "What kind of change is this pull request, judged by what the diff actually does",
        "criteria": {
            "feature": "Adds new behavior that users or API callers can observe; supporting tests "
            "and docs for that behavior may be included",
            "bugfix": "Corrects wrong behavior of code that already existed; supporting tests and "
            "docs for that fix may be included",
            "refactor": "Restructures or cleans up code while keeping behavior the same",
            "deps": "Only bumps dependency versions, lockfiles or vendored packages",
            "docs": "Only changes documentation, comments, translations or examples",
            "config_infra": "Only changes CI, build, deployment, tooling or configuration files",
            "tests_only": "Only adds or changes automated tests",
            "mixed": "Combines two or more of the kinds above as independent changes and none of "
            "them accounts for most of the diff (for example a bug fix plus an unrelated refactor "
            "plus a dependency bump)",
        },
    },
    "risk": {
        "type": "score",
        "instructions": "Which is the most sensitive kind of code that the diff adds, removes or modifies",
        "criteria": [
            (
                "Nothing that runs in production: only documentation, comments, tests, formatting, "
                "translations, dependency version bumps or developer-only tooling"
            ),
            ("Production runtime code, and none of it is in the critical list of the next level"),
            (
                "Critical production code: authentication, authorization or secret handling; "
                "database migrations or persisted data structure; removal or signature change of a "
                "public interface; shared infrastructure or deployment; calculation or movement of "
                "money; locks, transactions, retries, idempotency or cache invalidation; or code "
                "that deletes, truncates or overwrites persisted data"
            ),
        ],
    },
    "touches_auth_security": _noul(
        "The diff changes security-sensitive logic",
        true="Code that performs authentication, authorization, permission checks, cryptography, "
        "secret handling, session management or input sanitization is added, removed or modified",
        false="Security words only appear in file names, comments, docs, tests, translations or "
        "identifiers, or no security logic is changed",
    ),
    "touches_data_schema": _noul(
        "The diff changes the structure of persisted data",
        true="A database migration, a table, column or index definition, an ORM model field, or a "
        "stored file or message format is added, removed or modified",
        false="Only queries, in-memory types, API payloads or test fixtures change, or persisted data "
        "structure is untouched",
    ),
    "breaking_api": _noul(
        "The diff visibly breaks existing callers of a public interface",
        true="The diff removes, renames or changes the required inputs or the outputs of something "
        "visibly marked as public in the diff itself: an HTTP route, an exported symbol (__all__, "
        "export, pub, public), a CLI flag, or a documented configuration key or message format",
        false="Only backwards-compatible additions or deprecation warnings, changes to internal or "
        "private code, or nothing in the diff shows that the changed item is public",
    ),
    "touches_infra_ci": _noul(
        "The diff changes how the project is built, tested in CI or deployed",
        true="CI workflows, Dockerfiles, deployment manifests, infrastructure-as-code or build "
        "pipeline definitions are added, removed or modified",
        false="Only application code, tests, docs or dependency versions change",
    ),
    "has_tests": _noul(
        "The pull request includes automated tests for what it changes",
        true="Test files are added or modified in this pull request and they exercise the behavior "
        "being changed",
        false="No test file is changed, or the only test changes are unrelated to the behavior "
        "being changed",
    ),
    "description_explains_why": _noul(
        "The pull request description explains why the change is being made",
        true="The description states the motivation, the problem being solved or links the issue it "
        "resolves, beyond restating the title",
        false="The description is empty, is an unfilled template, or only lists what was changed",
    ),
}
