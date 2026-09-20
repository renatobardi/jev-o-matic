"""Lab 02 — fan-out: o que acontece com latência, custo e respostas quando N perguntas
vão na mesma chamada?

Mede, sobre o MESMO state:
  A. batched   : 1 chamada com N perguntas, N ∈ NS           (R repetições, mediana)
  B. sequential: N chamadas de 1 pergunta, uma após a outra  (soma das medianas)
  C. parallel  : N chamadas de 1 pergunta em threads         (wall-clock, R repetições)
  D. drift     : a resposta de cada pergunta muda entre sozinha (N=1) e em lote (N=max)?
"""

from __future__ import annotations

import json
import statistics as st
import time
from concurrent.futures import ThreadPoolExecutor

from harness import JevClient, choice, noul, score
from harness.client import ROOT, RunLog

NS = [1, 2, 5, 10, 20]
R = 5  # repetições por ponto

STATE = {
    "ticket": {
        "subject": "Cobrança duplicada e app travando",
        "message": (
            "Fui cobrado duas vezes na fatura de setembro e o app trava toda vez que abro a tela de "
            "pagamentos. Já é a terceira vez que reclamo e ninguém resolve. Sou cliente há 6 anos, "
            "plano empresarial. Se não estornarem até sexta eu cancelo e vou pro concorrente."
        ),
    },
    "customer": {"plan": "enterprise", "tenure_years": 6, "open_tickets": 3},
}

# 20 perguntas independentes, tipos misturados. A ordem define quem entra em cada N.
Q: dict[str, dict] = {
    "refund_wanted": noul("The customer explicitly asks for a refund"),
    "department": choice("Which team should handle this", {
        "billing": "Payments, charges, invoices, refunds",
        "technical": "Bugs, crashes, integration problems",
        "sales": "Pricing, plans, upgrades",
        "retention": "Cancellation threats, churn risk"}),
    "frustration": score("How frustrated is the customer",
                         ["Calm, just stating facts", "Frustrated but civil", "Very angry"]),
    "churn_threat": noul("The customer threatens to cancel or leave"),
    "has_bug": noul("The customer reports a software defect"),
    "urgency": score("How urgent is this ticket",
                     ["Can wait", "Should be handled this week", "Needs action today"]),
    "repeat_contact": noul("The customer says they already contacted support before about this"),
    "mentions_competitor": noul("The customer mentions a competitor"),
    "has_deadline": noul("The customer gives a specific deadline"),
    "language": choice("Language of the message", {
        "pt": "Portuguese", "en": "English", "es": "Spanish"}),
    "multi_issue": noul("The ticket contains more than one distinct problem"),
    "sentiment": score("Overall sentiment", ["Negative", "Neutral", "Positive"]),
    "customer_value": score("How valuable is this customer based on the data",
                            ["Low value", "Medium value", "High value"]),
    "needs_human": noul("This ticket should be escalated to a human agent"),
    "polite": noul("The customer is polite"),
    "asks_question": noul("The customer asks a direct question"),
    "product_area": choice("Which product area is affected", {
        "payments_screen": "Payment screen or checkout", "login": "Login or authentication",
        "reports": "Reports or exports", "other": "Anything else"}),
    "legal_risk": noul("The customer mentions lawyers, lawsuits or regulators"),
    "clarity": score("How clearly is the problem described",
                     ["Vague", "Understandable", "Very clear and specific"]),
    "spam": noul("This message is spam or not a real support request"),
}
assert len(Q) == max(NS)


def med(xs: list[float]) -> float:
    return round(st.median(xs), 1)


def main() -> None:
    client = JevClient()
    log = RunLog("02_fanout")
    keys = list(Q)

    client.decide(STATE, {keys[0]: Q[keys[0]]})  # warm-up: tira cold start da medição

    # --- A. batched ---------------------------------------------------------
    batched: dict[int, dict] = {}
    last_batch = None
    for n in NS:
        qs = {k: Q[k] for k in keys[:n]}
        runs = []
        for r in range(R):
            d = client.decide(STATE, qs)
            log.write(f"batched-n{n}-r{r}", d, mode="batched", n=n)
            runs.append(d)
        last_batch = runs[-1]
        batched[n] = {
            "lat_med": med([d.latency_ms for d in runs]),
            "lat_min": min(d.latency_ms for d in runs),
            "lat_max": max(d.latency_ms for d in runs),
            "in_tok": runs[0].input_tokens,
            "out_tok": runs[0].output_tokens,
            "cost": runs[0].cost,
        }

    # --- B. sequential (1 pergunta por chamada) -----------------------------
    single: dict[str, dict] = {}
    for k in keys:
        runs = []
        for r in range(3):
            d = client.decide(STATE, {k: Q[k]})
            log.write(f"single-{k}-r{r}", d, mode="single", n=1)
            runs.append(d)
        single[k] = {
            "lat_med": med([d.latency_ms for d in runs]),
            "in_tok": runs[0].input_tokens,
            "cost": runs[0].cost or 0.0,
            "value": runs[0].value(k),
            "values": [d.value(k) for d in runs],
        }

    # --- C. parallel (N chamadas simultâneas) -------------------------------
    parallel: dict[int, float] = {}
    for n in NS[1:]:
        walls = []
        for _ in range(3):
            t0 = time.perf_counter()
            with ThreadPoolExecutor(max_workers=n) as ex:
                list(ex.map(lambda k: client.decide(STATE, {k: Q[k]}), keys[:n]))
            walls.append((time.perf_counter() - t0) * 1000)
        parallel[n] = med(walls)

    # --- tabela -------------------------------------------------------------
    print(f"\nmodelo={last_batch.model}  R={R}\n")
    print(f"{'N':>3} | {'batched ms (min–max)':>24} | {'seq ms':>8} | {'par ms':>8} | "
          f"{'in_tok':>6} | {'Σtok 1×1':>8} | {'cost batch':>10} | {'Σcost 1×1':>10}")
    print("-" * 104)
    rows = []
    for n in NS:
        b = batched[n]
        seq = round(sum(single[k]["lat_med"] for k in keys[:n]), 1)
        tok1 = sum(single[k]["in_tok"] for k in keys[:n])
        cost1 = sum(single[k]["cost"] for k in keys[:n])
        par = parallel.get(n, single[keys[0]]["lat_med"])
        rows.append({"n": n, **b, "seq_ms": seq, "par_ms": par, "tok_single_sum": tok1, "cost_single_sum": cost1})
        rng = f"{b['lat_med']} ({b['lat_min']:.0f}–{b['lat_max']:.0f})"
        print(f"{n:>3} | {rng:>24} | {seq:>8} | {par:>8} | {b['in_tok']:>6} | {tok1:>8} | "
              f"{(b['cost'] or 0):>10.2e} | {cost1:>10.2e}")

    # --- D. drift: sozinha vs em lote ---------------------------------------
    print(f"\ndrift: resposta sozinha (N=1) vs no lote de {max(NS)}")
    print(f"{'pergunta':22} {'tipo':7} {'solo':>10} {'lote':>10} {'Δ':>7}  ruído solo (3 runs)")
    drift = []
    for k in keys:
        solo, lote = single[k]["value"], last_batch.value(k)
        t = Q[k]["type"]
        if t == "choice":
            delta = "=" if solo == lote else "MUDOU"
            noise = "estável" if len(set(single[k]["values"])) == 1 else f"{single[k]['values']}"
        else:
            delta = f"{lote - solo:+.2f}"
            noise = f"±{(max(single[k]['values']) - min(single[k]['values'])) / 2:.3f}"
        drift.append({"q": k, "type": t, "solo": solo, "batch": lote, "solo_runs": single[k]["values"]})
        print(f"{k:22} {t:7} {solo!s:>10} {lote!s:>10} {delta:>7}  {noise}")

    summary = ROOT / "results" / "02_fanout" / (log.path.stem + ".summary.json")
    summary.write_text(json.dumps({"model": last_batch.model, "R": R, "table": rows, "drift": drift},
                                  indent=2, ensure_ascii=False))
    print(f"\nlog: {log.path}\nsummary: {summary}")


if __name__ == "__main__":
    main()
