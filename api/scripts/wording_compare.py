"""Compara uma versão nova das perguntas (QUESTIONS_VERSION) com a anterior nos mesmos PRs (#12).

Só jev, sem LLM: ~14 chamadas, < US$ 0,01. A base é o bake-off (results/v2_llm_bakeoff/*.json), que
guardou as respostas do jev com o wording antigo pros mesmos 14 PRs. Sem ground truth: mede
incerteza e mudança de via, não acerto — acerto é o lab 09.

Autocontido: roda dentro do container da api (scripts/ops/compare-wording.sh faz tudo):
    docker compose exec -T api python - < api/scripts/wording_compare.py > novo.json
    python3 api/scripts/wording_compare.py --analyze novo.json base_bakeoff.json
Progresso vai pra stderr; o JSON, pra stdout."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

T = 0.7
KEYS = ["touches_auth_security", "touches_data_schema", "breaking_api", "risk", "change_type"]
PRS = [  # os mesmos do llm_bakeoff.py (os 7 primeiros = smoke do M1)
    "https://github.com/fastapi/fastapi/pull/13000",
    "https://github.com/fastapi/fastapi/pull/16289",
    "https://github.com/pallets/werkzeug/pull/3252",
    "https://github.com/pallets/flask/pull/5945",
    "https://github.com/pydantic/pydantic/pull/720",
    "https://github.com/django/django/pull/18000",
    "https://github.com/wagtail/wagtail/pull/12409",
    "https://github.com/django/django/pull/21441",
    "https://github.com/django/django/pull/21438",
    "https://github.com/encode/django-rest-framework/pull/9880",
    "https://github.com/wagtail/wagtail/pull/13323",
    "https://github.com/pallets/click/pull/1779",
    "https://github.com/fastapi/full-stack-fastapi-template/pull/2102",
    "https://github.com/encode/httpx/pull/3335",
]


async def run() -> None:
    from jevomatic_api.github import fetch_pr, parse_pr_url
    from jevomatic_api.jev import decide
    from jevomatic_api.questions import QUESTIONS, QUESTIONS_VERSION
    from jevomatic_api.state import build_state, runtime_files
    from jevomatic_api.verdict import verdict

    rows = []
    for url in PRS:
        try:
            pr = await fetch_pr(parse_pr_url(url))
            built = build_state(pr)
            res = await decide(built.state, QUESTIONS)
        except Exception as e:  # noqa: BLE001 — smoke: registra e segue
            print(f"✗ {url}: {e}", file=sys.stderr)
            continue
        runtime = runtime_files(built.categories)
        v = verdict(res.answers, pr.changed_files, T, runtime)
        rows.append(
            {
                "url": url,
                "title": pr.title,
                "files": pr.changed_files,
                "runtime_files": runtime,
                "categories": built.categories,
                "jev": {
                    k: {
                        "value": a.value,
                        "confidence": a.confidence,
                        "probabilities": a.probabilities,
                    }
                    for k, a in res.answers.items()
                },
                "lane": v.lane,
                "uncertain": v.uncertain,
                "reasons": v.reasons,
                "cost": res.cost,
            }
        )
        print(f"✓ {url} → {v.lane} {v.uncertain}", file=sys.stderr)
    json.dump(
        {"questions": QUESTIONS_VERSION, "t": T, "rows": rows}, sys.stdout, ensure_ascii=False
    )


def _old_lane(jev: dict[str, Any], files: int) -> str:
    """Via do wording antigo pela regra ANTIGA (sem guarda de runtime). Cópia mínima do verdict.py
    só pra via — o --analyze roda no Mac com python3 puro, sem o pacote instalado."""
    flags = KEYS[:3]
    sure = {k: jev[k]["confidence"] >= T for k in KEYS}
    if any(sure[k] and jev[k]["value"] >= 0.5 for k in flags) or (
        sure["risk"] and round(jev["risk"]["value"]) == 2
    ):
        return "senior"
    cold = all(sure[k] and jev[k]["value"] < 0.5 for k in flags)
    fast_type = sure["change_type"] and jev["change_type"]["value"] in {
        "docs",
        "tests_only",
        "deps",
    }
    if fast_type and cold and files <= 25 and sure["risk"] and round(jev["risk"]["value"]) == 0:
        return "fast"
    return "normal"


def analyze(new_path: str, base_path: str) -> int:
    new = json.loads(Path(new_path).read_text(encoding="utf-8"))
    base = {r["url"]: r for r in json.loads(Path(base_path).read_text(encoding="utf-8"))["rows"]}
    order = {"fast": 0, "normal": 1, "senior": 2}
    print(f"wording novo: {new['questions']} · t={new['t']} · {len(new['rows'])} PRs\n")
    print(f"{'PR':<46} {'risk conf':>13} {'type conf':>13}  via (antigo → novo)")
    unsure = {"old": {k: 0 for k in KEYS}, "new": {k: 0 for k in KEYS}}
    smoke7 = {"old": 0, "new": 0}
    changed = []
    for i, r in enumerate(new["rows"]):
        b = base.get(r["url"])
        if not b:
            continue
        for k in KEYS:
            unsure["old"][k] += b["jev"][k]["confidence"] < T
            unsure["new"][k] += r["jev"][k]["confidence"] < T
        if i < 7:
            smoke7["old"] += b["jev"]["risk"]["confidence"] < T
            smoke7["new"] += r["jev"]["risk"]["confidence"] < T
        old_lane = _old_lane(b["jev"], b["files"])
        slug = r["url"].removeprefix("https://github.com/").replace("/pull/", "#")
        o, n = b["jev"], r["jev"]
        mark = "" if old_lane == r["lane"] else "  ← mudou"
        print(
            f"{slug:<46} {o['risk']['confidence']:>5.2f} → {n['risk']['confidence']:<5.2f} "
            f"{o['change_type']['confidence']:>5.2f} → {n['change_type']['confidence']:<5.2f}  "
            f"{old_lane} → {r['lane']} [{o['change_type']['value']} → {n['change_type']['value']}]{mark}"
        )
        if old_lane != r["lane"]:
            changed.append((slug, old_lane, r["lane"], r["reasons"], r["title"]))
    print("\ndecisões abaixo de t (antigo → novo):")
    for k in KEYS:
        print(f"  {k:<24} {unsure['old'][k]:>2} → {unsure['new'][k]}")
    print(
        f"\ncritério de aceite (#12): risk incerto nos 7 do smoke: {smoke7['old']} → {smoke7['new']} (meta ≤ 3)"
    )
    if changed:
        print("\nvias que mudaram — LER O DIFF de cada uma antes de aceitar:")
        for slug, a, b_, reasons, title in changed:
            worse = "sobe" if order.get(b_, 1) > order.get(a, 1) else "desce"
            print(f"  {slug}: {a} → {b_} ({worse}) {reasons}\n    {title[:90]}")
    ok = smoke7["new"] <= 3
    print(
        "\n"
        + (
            "ACEITE: meta do risk batida; confira as vias que mudaram."
            if ok
            else "NÃO bateu a meta do risk."
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--analyze":
        sys.exit(analyze(sys.argv[2], sys.argv[3]))
    asyncio.run(run())
