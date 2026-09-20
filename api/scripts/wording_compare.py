"""Compara uma versão nova das perguntas (QUESTIONS_VERSION) com a anterior nos mesmos PRs (#12).

Só jev, sem LLM: ~19 chamadas, < US$ 0,01. A base é o bake-off (results/v2_llm_bakeoff/*.json), que
guardou as respostas do jev com o wording antigo pros mesmos 14 PRs. Sem ground truth: mede
incerteza e mudança de via, não acerto — acerto é o lab 09.

Autocontido: roda dentro do container da api (scripts/ops/compare-wording.sh faz tudo):
    docker compose exec -T api python - < api/scripts/wording_compare.py > novo.json
    python3 api/scripts/wording_compare.py --analyze   # pega o mais recente de cada pasta em results/
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
# Bugfixes banais (arquivos conferidos na API do GitHub: 1–2 arquivos de lógica comum + teste +
# changelog, nada da lista crítica). Sem base antiga: servem pra ver se o nível 1 do risk existe.
BANAL = [
    "https://github.com/pallets/click/pull/3865",  # abreviação do short help
    "https://github.com/Textualize/rich/pull/3180",  # wrap de caractere de largura dupla
    "https://github.com/Textualize/rich/pull/2820",  # pretty de dataclass vazia
    "https://github.com/pallets/jinja/pull/1852",  # f-string na geração de código
    "https://github.com/pallets/jinja/pull/2061",  # default de Environment.overlay
]
BANAL_MIN = 3  # aceite: pelo menos 3 de 5 no nível 1 com confidence ≥ t


async def run() -> None:
    from jevomatic_api.github import fetch_pr, parse_pr_url
    from jevomatic_api.jev import decide
    from jevomatic_api.questions import QUESTIONS, QUESTIONS_VERSION
    from jevomatic_api.state import build_state, runtime_files
    from jevomatic_api.verdict import verdict

    rows = []
    for url in [*PRS, *BANAL]:
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


def _slug(url: str) -> str:
    return url.removeprefix("https://github.com/").replace("/pull/", "#")


def _latest(folder: str) -> Path:
    """Arquivo mais recente de results/<folder>. Sem caminho vindo de fora: os nomes são fixos."""
    files = sorted((Path(__file__).resolve().parents[2] / "results" / folder).glob("*.json"))
    if not files:
        sys.exit(f"nada em results/{folder}/")
    return files[-1]


def _compare(rows: list[dict[str, Any]], base: dict[str, Any]) -> tuple[int, int]:
    """Tabela antigo → novo nos PRs que têm base. Devolve o risk incerto nos 7 do smoke."""
    order = {"fast": 0, "normal": 1, "senior": 2}
    print(f"{'PR':<46} {'risk conf':>13} {'type conf':>13}  via (antigo → novo)")
    unsure = {"old": dict.fromkeys(KEYS, 0), "new": dict.fromkeys(KEYS, 0)}
    changed = []
    for r in rows:
        o, n = base[r["url"]]["jev"], r["jev"]
        for k in KEYS:
            unsure["old"][k] += o[k]["confidence"] < T
            unsure["new"][k] += n[k]["confidence"] < T
        old_lane = _old_lane(o, base[r["url"]]["files"])
        moved = old_lane != r["lane"]
        print(
            f"{_slug(r['url']):<46} {o['risk']['confidence']:>5.2f} → {n['risk']['confidence']:<5.2f} "
            f"{o['change_type']['confidence']:>5.2f} → {n['change_type']['confidence']:<5.2f}  "
            f"{old_lane} → {r['lane']} [{o['change_type']['value']} → {n['change_type']['value']}]"
            f"{'  ← mudou' if moved else ''}"
        )
        if moved:
            way = "sobe" if order[r["lane"]] > order[old_lane] else "desce"
            changed.append(
                f"  {_slug(r['url'])}: {old_lane} → {r['lane']} ({way}) {r['reasons']}\n    {r['title'][:90]}"
            )
    print("\ndecisões abaixo de t (antigo → novo):")
    for k in KEYS:
        print(f"  {k:<24} {unsure['old'][k]:>2} → {unsure['new'][k]}")
    if changed:
        print("\nvias que mudaram — LER O DIFF de cada uma antes de aceitar:")
        print("\n".join(changed))
    smoke = [r for r in rows if r["url"] in PRS[:7]]
    old7 = sum(base[r["url"]]["jev"]["risk"]["confidence"] < T for r in smoke)
    new7 = sum(r["jev"]["risk"]["confidence"] < T for r in smoke)
    return old7, new7


def _banal(rows: list[dict[str, Any]]) -> int:
    """Os banais não têm base antiga: só mostra se o nível 1 do risk existe."""
    print(
        f"\nbanais (sem base antiga) — o nível 1 do risk existe? meta ≥ {BANAL_MIN}/{len(BANAL)}:"
    )
    level1 = 0
    for r in rows:
        n = r["jev"]
        hit = n["risk"]["confidence"] >= T and round(n["risk"]["value"]) == 1
        level1 += hit
        probs = {k: round(v, 2) for k, v in (n["risk"].get("probabilities") or {}).items()}
        print(
            f"  {_slug(r['url']):<28} risk {n['risk']['value']:.2f} ({n['risk']['confidence']:.2f}) "
            f"{probs} · {n['change_type']['value']} ({n['change_type']['confidence']:.2f}) → "
            f"{r['lane']} {r['uncertain']}{'  ✓' if hit else ''}"
        )
    print(f"  nível 1 confiante: {level1}/{len(BANAL)}")
    return level1


def analyze() -> int:
    new_path, base_path = _latest("v2_wording"), _latest("v2_llm_bakeoff")
    new = json.loads(new_path.read_text(encoding="utf-8"))
    base = {r["url"]: r for r in json.loads(base_path.read_text(encoding="utf-8"))["rows"]}
    print(f"{new_path.name} × base {base_path.name}")
    print(f"wording novo: {new['questions']} · t={new['t']} · {len(new['rows'])} PRs\n")
    old7, new7 = _compare([r for r in new["rows"] if r["url"] in base], base)
    print(f"\ncritério de aceite (#12): risk incerto nos 7 do smoke: {old7} → {new7} (meta ≤ 3)")
    level1 = _banal([r for r in new["rows"] if r["url"] in BANAL])
    ok = new7 <= 3 and level1 >= BANAL_MIN
    print(
        "\n"
        + ("ACEITE: metas batidas; confira as vias que mudaram." if ok else "NÃO bateu as metas.")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--analyze"]:
        sys.exit(analyze())
    asyncio.run(run())
