"""Lab 01 — como é a resposta de cada primitivo (noul / choice / score)?
Sem métrica: só imprime a resposta normalizada + raw pra entender o formato."""

import json

from harness import JevClient, choice, noul, score
from harness.client import RunLog

TICKETS = {
    "pt": "Fui cobrado duas vezes na fatura de setembro. Quero o estorno hoje, já é a terceira vez que reclamo.",
    "en": "I was charged twice on my September invoice. I want a refund today, this is the third time I complain.",
}

QUESTIONS = {
    "refund_wanted": noul("The customer explicitly asks for a refund"),
    "department": choice(
        "Which team should handle this ticket",
        {
            "billing": "Payments, charges, invoices, refunds",
            "technical": "Bugs, errors, integration problems",
            "sales": "Pricing, plans, upgrades",
        },
    ),
    "frustration": score(
        "How frustrated is the customer",
        ["Calm, just stating facts", "Frustrated but civil", "Very angry"],
    ),
}


def main() -> None:
    client = JevClient()
    log = RunLog("01_primitives")
    for lang, ticket in TICKETS.items():
        d = client.decide({"ticket": ticket}, QUESTIONS)
        log.write(lang, d)
        print(f"\n=== {lang} | {d.latency_ms}ms | in={d.input_tokens} out={d.output_tokens} cost={d.cost}")
        for k, a in d.answers.items():
            print(f"  {k:14} {a['type']:7} value={a['value']!s:10} conf={a['confidence']} probs={a['probabilities']}")
    print("\n--- raw (último) ---")
    print(json.dumps(d.raw, indent=2, ensure_ascii=False))
    print(f"\nlog: {log.path}")


if __name__ == "__main__":
    main()
