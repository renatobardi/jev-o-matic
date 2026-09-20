"""Lab 00 — roda o dataset rotulado inteiro (PT e EN) com um conjunto fixo de perguntas.
É a única etapa que chama a API; labs 03 (threshold), 07 (PT vs EN) e 08 (calibração)
são análises offline em cima do JSONL gerado aqui.

Instruções sempre em inglês: isola o efeito do idioma do TICKET."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from harness import JevClient, choice, noul, score
from harness.client import ROOT, RunLog

DATASET = ROOT / "datasets" / "tickets_v1.jsonl"
WORKERS = 8

QUESTIONS = {
    "department": choice("Which team should handle this support ticket first", {
        "billing": "Charges, invoices, payment methods, refunds",
        "technical": "Bugs, errors, outages, performance, how-to and API questions",
        "sales": "Pricing, plans, upgrades, quotes, demos, new seats",
        "retention": "Cancellation, downgrade, churn threats, contract termination or renegotiation",
    }),
    "urgency": score("How urgent is this ticket", [
        "Can wait, no time pressure",
        "Should be resolved this week",
        "Needs action today: operation blocked, imminent deadline or ongoing financial damage",
    ]),
    "refund_wanted": noul("The customer wants money returned to them, stated explicitly or clearly implied"),
    "churn_threat": noul("The customer threatens, announces or requests to cancel, downgrade or leave"),
    "has_bug": noul("The customer reports a software defect or malfunction"),
}


def hit(key: str, value, labels: dict) -> bool:
    if key == "department":
        return value in (labels["department"], labels["alt_department"])
    if key == "urgency":
        return round(value) == labels["urgency"]
    return (value >= 0.5) == labels[key]


def main() -> None:
    items = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines()]
    client = JevClient()
    log = RunLog("00_dataset_run")
    jobs = [(it, lang) for it in items for lang in ("pt", "en")]

    client.decide({"ticket": "warm-up"}, {"has_bug": QUESTIONS["has_bug"]})
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        decisions = list(ex.map(lambda j: client.decide({"ticket": j[0]["text"][j[1]]}, QUESTIONS), jobs))

    acc: dict[str, dict[str, list[bool]]] = {"pt": {}, "en": {}}
    cost = 0.0
    for (it, lang), d in zip(jobs, decisions):
        hits = {k: hit(k, d.value(k), it["labels"]) for k in QUESTIONS}
        log.write(f"{it['id']}-{lang}", d, expected=it["labels"], lang=lang,
                  difficulty=it["difficulty"], tags=it["tags"], hits=hits)
        cost += d.cost or 0.0
        for k, h in hits.items():
            acc[lang].setdefault(k, []).append(h)

    print(f"\n{len(jobs)} chamadas · custo total ${cost:.5f} · modelo {decisions[-1].model}\n")
    print(f"{'pergunta':16} {'PT':>7} {'EN':>7}")
    for k in QUESTIONS:
        pt, en = acc["pt"][k], acc["en"][k]
        print(f"{k:16} {sum(pt) / len(pt):>7.1%} {sum(en) / len(en):>7.1%}")
    print(f"\nlog: {log.path}")


if __name__ == "__main__":
    main()
