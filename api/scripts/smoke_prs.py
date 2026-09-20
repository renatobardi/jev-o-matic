"""Smoke do M1 com PRs reais (issue #15). Chama o pipeline direto, sem subir servidor.

    cd api && uv run python scripts/smoke_prs.py          # jev real (usa ../.env)
    JEV_BACKEND=mock uv run python scripts/smoke_prs.py   # sem gastar nada

Grava o JSON completo em ../results/v2_smoke/<timestamp>.json."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (o que se espera ver, URL) — expectativa informal, não é ground truth.
PRS = [
    ("docs/tradução → fast", "https://github.com/fastapi/fastapi/pull/13000"),
    ("bump de dependência → fast/deps", "https://github.com/fastapi/fastapi/pull/16289"),
    (
        "docs + refactor de secure_filename (sanitização) → security sim; o LLM deu senior",
        "https://github.com/pallets/werkzeug/pull/3252",
    ),
    ("workflow de CI → infra, config_infra", "https://github.com/pallets/flask/pull/5945"),
    ("remove código deprecated → breaking_api?", "https://github.com/pydantic/pydantic/pull/720"),
    ("bugfix pequeno em código → normal", "https://github.com/django/django/pull/18000"),
    ("migração de streamfield → schema?", "https://github.com/wagtail/wagtail/pull/12409"),
]


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


async def main() -> None:
    load_env()
    from jevomatic_api.errors import TriageError
    from jevomatic_api.triage import triage

    out = []
    for expect, url in PRS:
        try:
            r = await triage(url)  # guardas novas a cada chamada: sem cache nem limite
        except TriageError as e:
            print(f"\n✗ {url}\n  {e.code}: {e.message}")
            continue
        out.append({"expect": expect, "url": url, **r.model_dump()})
        d = r.decisions
        jev = next(s for s in r.trace if s.stage == "jev")
        gh = next(s for s in r.trace if s.stage == "github")
        print(f"\n{r.pr.slug} — {r.pr.title[:70]}\n  esperado: {expect}")
        print(
            f"  lane={r.verdict.lane} reasons={r.verdict.reasons} uncertain={r.verdict.uncertain}"
        )
        llm = next(s for s in r.trace if s.stage == "llm")
        if not llm.skipped:
            print(
                f"  cascata: jev sozinho={r.verdict.jev_lane} → LLM respondeu {r.verdict.escalated} "
                f"em {llm.latency_ms:.0f}ms (${llm.cost or 0:.6f})"
            )
            for k in r.verdict.escalated:
                dk = r.decisions[k]
                was = dk.original.value if dk.original else "?"
                print(f"    {k}: jev {was} → LLM {dk.value} — {dk.rationale}")
        elif llm.note != "nenhuma decisão incerta":
            print(f"  cascata: {llm.note}")
        print(
            f"  change_type={d['change_type'].value} ({d['change_type'].confidence:.2f}) · "
            f"risk={d['risk'].value:.2f} ({d['risk'].confidence:.2f})"
        )
        print("  " + " · ".join(f"{k}={d[k].value:.2f}" for k in d if d[k].type == "noul"))
        print(
            f"  github {gh.latency_ms:.0f}ms · jev {jev.latency_ms:.0f}ms · ${jev.cost or 0:.6f} · "
            f"tokens reais {jev.input_tokens} vs estimados {r.sent.tokens_est} · "
            f"arquivos {len(r.sent.files_included)}/{r.sent.files_total} "
            f"(trunc {len(r.sent.files_truncated)}, omit {len(r.sent.files_omitted)})"
        )

    dest = ROOT / "results" / "v2_smoke" / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n{len(out)}/{len(PRS)} ok · {dest}")


if __name__ == "__main__":
    asyncio.run(main())
