"""Perguntas de triagem de PR. Mudou o wording → bump em QUESTIONS_VERSION (invalida cache e
muda o que a demo mede — lab 00 v3: o wording define o conceito).

Regras dos labs aplicadas:
- escopo explícito: "the diff adds/removes/modifies …", nunca "mentions" (lab 06: genérico casa palavra-chave)
- `criteria` true/false com os quase-positivos conhecidos no false (lab 06 v3)
- relação dentro de UMA pergunta; nada de átomos pra compor depois (labs 04 e 06 v4)
- score com níveis mutuamente exclusivos, ancorados em estado observável (lab 04 u1)
- contagem e tamanho ficam em código, não aqui
"""

from __future__ import annotations

from typing import Any

QUESTIONS_VERSION = "pr-v1"

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
            "feature": "Adds new behavior that users or API callers can observe",
            "bugfix": "Corrects wrong behavior of code that already existed",
            "refactor": "Restructures or cleans up code while keeping behavior the same",
            "deps": "Only bumps dependency versions, lockfiles or vendored packages",
            "docs": "Only changes documentation, comments, translations or examples",
            "config_infra": "Only changes CI, build, deployment, tooling or configuration files",
            "tests_only": "Only adds or changes automated tests",
        },
    },
    "risk": {
        "type": "score",
        "instructions": "How much damage could a mistake in this pull request cause in production",
        "criteria": [
            (
                "None: the change cannot alter production runtime behavior (docs, comments, tests, "
                "formatting, translations, dev-only tooling)"
            ),
            (
                "Contained: changes runtime behavior in a limited area; a mistake would be noticed and "
                "reverted without lasting damage"
            ),
            (
                "Severe: a mistake could lose or corrupt data, open a security hole, cause an outage or "
                "break existing clients (authentication, permissions, payments, migrations, public API "
                "contracts, shared infrastructure)"
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
        "The diff breaks existing callers of a public interface",
        true="An existing public endpoint, exported function, CLI flag, configuration key or message "
        "format is removed, renamed, or changes its required inputs or its outputs",
        false="Only backwards-compatible additions, internal changes, or no public interface is touched",
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
