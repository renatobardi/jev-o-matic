"""Lab 05 — cascata jev → LLM: quanto economiza vs mandar tudo pro LLM, e o LLM acerta
justamente onde o jev está inseguro?

- jev: reaproveita o último run do lab 00 (nenhuma chamada nova ao jev).
- LLM: roda TODOS os tickets (baseline "tudo no LLM"), 1 chamada por ticket respondendo as 4 perguntas em JSON.
- Cascata simulada offline: por ticket, se TODAS as 4 respostas do jev têm conf ≥ t → fica no jev;
  senão paga 1 chamada de LLM e usa o LLM nas perguntas com conf < t.

uv run lab 05            → chama o LLM e analisa     (LLM_MODEL no .env troca o modelo)
uv run lab 05 --offline  → reanalisa o último run"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx

from harness.analysis import latest_run
from harness.client import ROOT

KEYS = ["department", "refund_wanted", "churn_threat", "has_bug"]
THRESHOLDS = [0.5, 0.7, 0.8, 0.9, 0.95]
LLM_MODEL = os.getenv("LLM_MODEL", "~openai/gpt-sol-latest")

SYSTEM = """You triage customer support tickets for a B2B SaaS company. Tickets may be in Portuguese or English.
Answer ONLY with a JSON object with exactly these keys:
- "department": one of "billing" (charges, invoices, payment methods, refunds), "technical" (bugs, errors, outages, performance, how-to and API questions), "sales" (pricing, plans, upgrades, quotes, demos, new seats), "retention" (cancellation, downgrade, churn threats, contract termination or renegotiation). The team that should handle the ticket first.
- "refund_wanted": boolean. The customer wants money returned to them, explicitly or clearly implied.
- "churn_threat": boolean. The customer themselves threatens, announces or requests to cancel, downgrade or leave OUR service (not another vendor; withdrawn intentions do not count).
- "has_bug": boolean. The customer reports a defect or malfunction in OUR product affecting them now."""


def call_llm(text: str) -> dict:
    if os.getenv("JEV_BACKEND") == "mock":
        return {"answers": {"department": "billing", "refund_wanted": False, "churn_threat": False, "has_bug": False},
                "latency_ms": 900.0, "input_tokens": 300, "output_tokens": 40, "cost": 0.001, "model": "mock"}
    body = {"model": LLM_MODEL, "temperature": 0, "response_format": {"type": "json_object"},
            "usage": {"include": True},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]}
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "X-Title": "jev-o-matic"}
    # 400 costuma ser parâmetro não suportado pelo modelo: tenta de novo tirando um por vez
    drops = [(), ("temperature",), ("temperature", "response_format"), ("temperature", "response_format", "usage")]
    last = None
    for attempt, drop in enumerate(drops):
        try:
            t0 = time.perf_counter()
            r = httpx.post("https://openrouter.ai/api/v1/chat/completions",
                           json={k: v for k, v in body.items() if k not in drop}, headers=headers, timeout=120)
            lat = (time.perf_counter() - t0) * 1000
            if r.status_code >= 400:
                last = f"HTTP {r.status_code}: {r.text[:500]}"
                if r.status_code in (401, 402, 403, 404):
                    break
                time.sleep(1)
                continue
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            ans = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
            u = data.get("usage", {})
            return {"answers": ans, "latency_ms": round(lat, 1), "input_tokens": u.get("prompt_tokens"),
                    "output_tokens": u.get("completion_tokens"), "cost": u.get("cost"), "model": data.get("model", LLM_MODEL),
                    "dropped_params": list(drop)}
        except Exception as e:  # noqa: BLE001
            last = repr(e)
            time.sleep(1.5)
    raise SystemExit(f"LLM falhou ({LLM_MODEL}): {last}\n→ se for ID inválido, veja openrouter.ai/models e ajuste LLM_MODEL no .env")


def hit(key: str, value, labels: dict) -> bool:
    if key == "department":
        return value in (labels["department"], labels["alt_department"])
    return bool(value) == labels[key]


def p50(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2]


def analyze(jev_rows: list[dict], llm_rows: dict[str, dict]) -> None:
    rows = [r for r in jev_rows if r["id"] in llm_rows]
    n = len(rows)
    jev_cost = sum(r["cost"] or 0 for r in rows) / n
    llm_cost = sum(llm_rows[r["id"]]["cost"] or 0 for r in rows) / n
    jev_lat, llm_lat = p50([r["latency_ms"] for r in rows]), p50([llm_rows[r["id"]]["latency_ms"] for r in rows])
    model = llm_rows[rows[0]["id"]]["model"]

    def jev_hit(r, k):
        return r["hits"][k]

    def llm_hit(r, k):
        return hit(k, llm_rows[r["id"]]["answers"].get(k), r["expected"])

    print(f"n={n} tickets×idioma · LLM={model}")
    print(f"por ticket:  jev ${jev_cost:.6f} · {jev_lat:.0f}ms p50   |   LLM ${llm_cost:.6f} · {llm_lat:.0f}ms p50   "
          f"(LLM = {llm_cost / jev_cost:.0f}× custo, {llm_lat / jev_lat:.1f}× latência)\n")

    print(f"{'acerto':16}" + "".join(f"{k:>15}" for k in KEYS) + f"{'ticket 4/4':>12}")
    for name, fn in (("jev só", jev_hit), ("LLM só", llm_hit)):
        print(f"{name:16}" + "".join(f"{sum(fn(r, k) for r in rows) / n:>15.1%}" for k in KEYS)
              + f"{sum(all(fn(r, k) for k in KEYS) for r in rows) / n:>12.1%}")

    print("\nonde o jev está inseguro (conf < 0,8), quem acerta?")
    for k in KEYS:
        lo = [r for r in rows if r["answers"][k]["confidence"] < .8]
        if lo:
            print(f"  {k:15} n={len(lo):>3}  jev {sum(jev_hit(r, k) for r in lo) / len(lo):>6.1%}   LLM {sum(llm_hit(r, k) for r in lo) / len(lo):>6.1%}")
    hi_err = [(r["id"], k) for r in rows for k in KEYS if r["answers"][k]["confidence"] >= .8 and not jev_hit(r, k)]
    print(f"  erros do jev com conf ≥ 0,8 (a cascata não pega): {len(hi_err)} {hi_err[:6]}")

    print(f"\ncascata (ticket vai pro LLM se alguma das 4 respostas tem conf < t)")
    print(f"{'t':>6} {'% escalado':>11} {'ticket 4/4':>11} {'custo/ticket':>13} {'vs LLM só':>10} {'lat média':>10} {'lat p50':>8}")
    for t in THRESHOLDS:
        esc, ok, cost, lats = 0, 0, 0.0, []
        for r in rows:
            low = [k for k in KEYS if r["answers"][k]["confidence"] < t]
            L = llm_rows[r["id"]]
            ok += all(llm_hit(r, k) if k in low else jev_hit(r, k) for k in KEYS)
            cost += (r["cost"] or 0) + ((L["cost"] or 0) if low else 0)
            lats.append(r["latency_ms"] + (L["latency_ms"] if low else 0))
            esc += bool(low)
        print(f"{t:>6.2f} {esc / n:>11.1%} {ok / n:>11.1%} {cost / n:>13.6f} {cost / n / llm_cost:>10.1%} "
              f"{sum(lats) / n:>9.0f}ms {p50(lats):>6.0f}ms")


def main() -> None:
    jev_path, jev_rows = latest_run("00_dataset_run")
    out_dir = ROOT / "results" / "05_cascade"
    if "--offline" in sys.argv:
        path, rows = latest_run("05_cascade")
        print(f"offline: jev={jev_path.name} llm={path.name}\n")
        return analyze(jev_rows, {r["id"]: r for r in rows})

    ds = {}
    for l in (ROOT / "datasets" / "tickets_v1.1.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(l)
        ds[d["id"]] = d
    jobs = [(r["id"], ds[r["id"][:4]]["text"][r["lang"]]) for r in jev_rows]
    call_llm(jobs[0][1])  # warm-up + valida o modelo antes de disparar tudo
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(lambda j: call_llm(j[1]), jobs))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for (rid, _), r in zip(jobs, res):
            f.write(json.dumps({"id": rid, **r}, ensure_ascii=False) + "\n")
    print(f"{len(jobs)} chamadas LLM · ${sum(r['cost'] or 0 for r in res):.4f}\njev: {jev_path.name}\nllm: {path}\n")
    analyze(jev_rows, {rid: r for (rid, _), r in zip(jobs, res)})


if __name__ == "__main__":
    main()
