"""Bake-off de LLMs pra etapa de segunda opinião da cascata.

Pra cada PR: GitHub → state → jev (real) → e as MESMAS 5 perguntas que definem a via vão pra cada
modelo candidato, em paralelo. Não há ground truth: a referência é o modelo atual (sol) e, como
proxy, o jev quando está confiante (conf ≥ 0,8). As discordâncias saem com a justificativa de cada
modelo pra leitura humana contra o diff.

Autocontido de propósito: roda dentro do container da api (que só tem o pacote instalado):
    docker compose exec -T api python - < api/scripts/llm_bakeoff.py > resultado.json
    python api/scripts/llm_bakeoff.py --analyze resultado.json
Progresso vai pra stderr; o JSON, pra stdout."""

from __future__ import annotations

import asyncio
import json
import os
import statistics as st
import sys
import time
from typing import Any

REFERENCE = "~openai/gpt-sol-latest"
MODELS = [
    REFERENCE,
    "z-ai/glm-5.3",
    "~deepseek/deepseek-pro-latest",
    "moonshotai/kimi-k2.6",
    "~openai/gpt-luna-latest",
    "z-ai/glm-5.3-flash",
]
MAX_TOKENS = 3000  # modelos de raciocínio gastam o limite pensando

# "hint" é palpite pelo TÍTULO, não verificado no diff (lição do werkzeug#3252). Não é rótulo.
PRS = [
    ("tradução de docs", "https://github.com/fastapi/fastapi/pull/13000"),
    ("bump de dependência (só lockfile)", "https://github.com/fastapi/fastapi/pull/16289"),
    (
        "docs + refactor de secure_filename — verificado no diff",
        "https://github.com/pallets/werkzeug/pull/3252",
    ),
    ("workflow de CI (scanner de segurança)", "https://github.com/pallets/flask/pull/5945"),
    ("remove código deprecated", "https://github.com/pydantic/pydantic/pull/720"),
    ("remove função interna", "https://github.com/django/django/pull/18000"),
    ("fix em migração de streamfield", "https://github.com/wagtail/wagtail/pull/12409"),
    (
        "CVE: troca checagem por substring em Cache-Control",
        "https://github.com/django/django/pull/21441",
    ),
    ("CVE: helper pra dividir valores de header", "https://github.com/django/django/pull/21438"),
    (
        "typo num .md chamado authentication — armadilha de palavra-chave?",
        "https://github.com/encode/django-rest-framework/pull/9880",
    ),
    ("feature: reordenação na IndexView", "https://github.com/wagtail/wagtail/pull/13323"),
    ("adiciona um teste", "https://github.com/pallets/click/pull/1779"),
    (
        "bump do uv no Dockerfile",
        "https://github.com/fastapi/full-stack-fastapi-template/pull/2102",
    ),
    (
        "remove uso sobrecarregado de verify/cert — quebra API?",
        "https://github.com/encode/httpx/pull/3335",
    ),
]


def log(*a: Any) -> None:
    print(*a, file=sys.stderr, flush=True)


def level(key: str, value: Any) -> Any:
    """Resposta reduzida ao que decide a via: bool pros nouls, nível pro risk, rótulo pro tipo."""
    if value is None:
        return None
    if key == "change_type":
        return value
    if key == "risk":
        return round(float(value))
    return float(value) >= 0.5


async def run() -> None:
    from jevomatic_api.github import fetch_pr, parse_pr_url
    from jevomatic_api.jev import decide
    from jevomatic_api.llm import LlmUnavailable, second_opinion
    from jevomatic_api.questions import QUESTIONS
    from jevomatic_api.state import build_state
    from jevomatic_api.verdict import LANE_KEYS

    asked = {k: QUESTIONS[k] for k in LANE_KEYS}
    out: list[dict[str, Any]] = []
    limit = int(os.getenv("BAKEOFF_LIMIT", "0")) or len(PRS)  # BAKEOFF_LIMIT=3 pra ensaio
    for hint, url in PRS[:limit]:
        try:
            pr = await fetch_pr(parse_pr_url(url))
        except Exception as e:  # noqa: BLE001
            log(f"✗ {url}: {e!r}")
            continue
        built = build_state(pr)
        jev = await decide(built.state, QUESTIONS)
        row: dict[str, Any] = {
            "url": url,
            "hint": hint,
            "title": pr.title,
            "files": pr.changed_files,
            "tokens_est": built.sent.tokens_est,
            "jev": {
                k: {"value": jev.answers[k].value, "confidence": jev.answers[k].confidence}
                for k in LANE_KEYS
            },
            "jev_ms": jev.latency_ms,
            "jev_cost": jev.cost,
            "models": {},
        }

        async def one(model: str) -> tuple[str, dict[str, Any]]:
            t0 = time.perf_counter()
            try:
                r = await second_opinion(built.state, asked, model=model, max_tokens=MAX_TOKENS)  # noqa: B023
            except LlmUnavailable as e:
                return model, {
                    "error": str(e)[:300],
                    "latency_ms": round((time.perf_counter() - t0) * 1000),
                }
            return model, {
                "served_by": r.model,
                "latency_ms": r.latency_ms,
                "cost": r.cost,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "answers": {
                    k: {"value": a.answer.value, "reason": a.rationale}
                    for k, a in r.answers.items()
                },
            }

        for model, res in await asyncio.gather(*(one(m) for m in MODELS)):
            row["models"][model] = res
        ok = sum("answers" in v and len(v["answers"]) == len(asked) for v in row["models"].values())
        log(f"✓ {pr.ref.slug}: {ok}/{len(MODELS)} modelos responderam as {len(asked)} perguntas")
        out.append(row)
    json.dump(
        {"reference": REFERENCE, "models": MODELS, "keys": LANE_KEYS, "rows": out},
        sys.stdout,
        ensure_ascii=False,
        indent=1,
    )


def analyze(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    ref, keys, rows = data["reference"], data["keys"], data["rows"]
    total = len(rows) * len(keys)
    print(
        f"{len(rows)} PRs × {len(keys)} perguntas = {total} decisões por modelo · referência: {ref}\n"
    )
    print(
        f"{'modelo':34} {'válidas':>8} {'= sol':>7} {'= jev conf≥.8':>14} {'lat p50':>8} {'lat máx':>8} "
        f"{'US$/PR':>9} {'vs sol':>7} {'out tok':>8}"
    )
    ref_cost = None
    for m in data["models"]:
        valid = agree = agree_n = jv = jv_n = 0
        lats: list[float] = []
        costs: list[float] = []
        outs: list[int] = []
        for r in rows:
            res = r["models"].get(m, {})
            if "latency_ms" in res:
                lats.append(res["latency_ms"])
            if res.get("cost") is not None:
                costs.append(res["cost"])
            if res.get("output_tokens"):
                outs.append(res["output_tokens"])
            ans = res.get("answers", {})
            refans = r["models"].get(ref, {}).get("answers", {})
            for k in keys:
                mine = level(k, ans.get(k, {}).get("value"))
                if mine is None:
                    continue
                valid += 1
                theirs = level(k, refans.get(k, {}).get("value"))
                if theirs is not None:
                    agree_n += 1
                    agree += mine == theirs
                j = r["jev"][k]
                if j["confidence"] >= 0.8:
                    jv_n += 1
                    jv += mine == level(k, j["value"])
        cost = st.mean(costs) if costs else float("nan")
        if m == ref:
            ref_cost = cost
        ratio = f"{ref_cost / cost:.1f}×" if ref_cost and cost and m != ref else "—"
        print(
            f"{m:34} {valid:>4}/{total:<3} {(agree / agree_n if agree_n else 0):>7.0%} "
            f"{(jv / jv_n if jv_n else 0):>9.0%} ({jv_n:>2}) {(st.median(lats) if lats else 0):>7.0f}ms "
            f"{(max(lats) if lats else 0):>7.0f}ms {cost:>9.5f} {ratio:>7} {(st.mean(outs) if outs else 0):>8.0f}"
        )

    print("\nerros por modelo:")
    for m in data["models"]:
        errs = [r["models"][m]["error"] for r in rows if "error" in r["models"].get(m, {})]
        if errs:
            print(f"  {m}: {len(errs)}× — {errs[0][:140]}")

    print("\ndiscordâncias com a referência (ler contra o diff — não há ground truth):")
    for r in rows:
        refans = r["models"].get(ref, {}).get("answers", {})
        lines = []
        for k in keys:
            base = level(k, refans.get(k, {}).get("value"))
            diff = {
                m: level(k, r["models"][m].get("answers", {}).get(k, {}).get("value"))
                for m in data["models"]
                if m != ref
            }
            diff = {m: v for m, v in diff.items() if v is not None and v != base}
            if diff:
                j = r["jev"][k]
                lines.append(
                    f"    {k}: sol={base} · jev={level(k, j['value'])} (conf {j['confidence']:.2f}) · "
                    + " · ".join(f"{m.split('/')[-1]}={v}" for m, v in diff.items())
                )
        if lines:
            print(f"  {r['url']} — {r['title'][:60]}")
            print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--analyze":
        analyze(sys.argv[2])
    else:
        asyncio.run(run())
