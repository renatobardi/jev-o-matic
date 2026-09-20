"""Lab 04 — composite scoring: urgency (ponto fraco, 72–74%) melhora se quebrada em
dimensões atômicas combinadas em código?

Variantes (todas na mesma chamada, dataset v1.1 PT+EN):
  u0      score único, wording do lab 00, nível = round(score)
  u0fit   mesmo score, mas cortes ajustados no treino (testa se o viés pra cima é só deslocamento)
  u1      score único com critérios reescritos (mutuamente exclusivos, sem gatilho amplo)
  u2      composto a priori: nouls atômicos, regra fixa com corte 0.5
  u2fit   composto com 2 cortes (t1, t2) ajustados no treino
Treino = tickets de id ímpar, teste = id par (PT e EN do mesmo ticket ficam juntos).

uv run lab 04            → chama a API e analisa
uv run lab 04 --offline  → reanalisa o último run"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import product

from harness import JevClient, noul, score
from harness.analysis import latest_run
from harness.client import ROOT, RunLog

DATASET = ROOT / "datasets" / "tickets_v1.1.jsonl"

Q = {
    "u0": score("How urgent is this ticket", [
        "Can wait, no time pressure",
        "Should be resolved this week",
        "Needs action today: operation blocked, imminent deadline or ongoing financial damage",
    ]),
    "u1": score("How soon does the company need to act on this ticket", [
        "No action needed beyond answering: a question, information request or low-stakes change with no deadline",
        "Something must be fixed, refunded, cancelled or changed, but the author can keep operating meanwhile",
        "The author is blocked or harmed right now, or states a consequence that lands today or tomorrow",
    ]),
    # nível 2
    "blocked": noul("The author or their team cannot work or operate right now because of this problem"),
    "deadline_48h": noul("The author states a deadline or consequence that falls today or tomorrow"),
    "money_now": noul("The author is losing money right now or faces an imminent suspension or large wrongful debit"),
    "security": noul("The author reports data loss, data exposed to the wrong people or a security incident"),
    # nível 1
    "needs_action": noul("Resolving this requires the company to fix, refund, cancel or change something, not just answer a question"),
    "is_problem": noul("The author reports something that is wrong or not working as expected"),
    "deadline_soon": noul("The author mentions a date or deadline within the next few weeks"),
}
L2 = ["blocked", "deadline_48h", "money_now", "security"]
L1 = ["needs_action", "is_problem", "deadline_soon"]


def feats(r: dict) -> tuple[float, float]:
    a = r["answers"]
    return max(a[k]["value"] for k in L1), max(a[k]["value"] for k in L2)


def composite(r: dict, t1: float = .5, t2: float = .5) -> int:
    f1, f2 = feats(r)
    return 2 if f2 >= t2 else 1 if f1 >= t1 else 0


def cut(v: float, c1: float, c2: float) -> int:
    return 2 if v >= c2 else 1 if v >= c1 else 0


def fit(train: list[dict], pred) -> tuple[float, float]:
    grid = [x / 20 for x in range(1, 20)]
    return max(product(grid, grid), key=lambda p: sum(pred(r, *p) == r["expected"]["urgency"] for r in train))


def report(name: str, rows: list[dict], pred) -> None:
    y = [(r["expected"]["urgency"], pred(r)) for r in rows]
    acc = sum(e == p for e, p in y) / len(y)
    over = sum(p > e for e, p in y)
    under = sum(p < e for e, p in y)
    miss2 = sum(e == 2 and p < 2 for e, p in y)
    false2 = sum(e < 2 and p == 2 for e, p in y)
    far = sum(abs(e - p) == 2 for e, p in y)
    print(f"  {name:7} acc {acc:>6.1%} | acima {over:>3} abaixo {under:>3} | nível 2 perdido {miss2:>2} "
          f"falso nível 2 {false2:>3} | erro de 2 níveis {far}")


def analyze(rows: list[dict]) -> None:
    train = [r for r in rows if int(r["id"][1:4]) % 2 == 1]
    test = [r for r in rows if int(r["id"][1:4]) % 2 == 0]
    c0 = fit(train, lambda r, a, b: cut(r["answers"]["u0"]["value"], a * 2, b * 2))
    t = fit(train, composite)
    preds = {
        "u0": lambda r: round(r["answers"]["u0"]["value"]),
        "u0fit": lambda r: cut(r["answers"]["u0"]["value"], c0[0] * 2, c0[1] * 2),
        "u1": lambda r: round(r["answers"]["u1"]["value"]),
        "u2": composite,
        "u2fit": lambda r: composite(r, *t),
    }
    print(f"cortes ajustados no treino: u0fit score≥{c0[0] * 2:.2f}→1, ≥{c0[1] * 2:.2f}→2 · u2fit t1={t[0]:.2f} t2={t[1]:.2f}")
    for label, sel in (("TODOS", rows), ("TESTE (ids pares — o que vale pros *fit)", test),
                       ("PT", [r for r in rows if r["lang"] == "pt"]), ("EN", [r for r in rows if r["lang"] == "en"])):
        print(f"\n{label} (n={len(sel)})")
        for name, p in preds.items():
            report(name, sel, p)

    print("\nerros do u2 (composto a priori) — qual dimensão disparou/faltou")
    ds = {json.loads(l)["id"]: json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines()}
    for r in rows:
        if r["lang"] == "pt" and composite(r) != r["expected"]["urgency"]:
            a = r["answers"]
            top = ", ".join(f"{k}={a[k]['value']:.2f}" for k in L2 + L1 if a[k]["value"] >= .3)
            print(f"  {r['id'][:4]} exp={r['expected']['urgency']} got={composite(r)} [{top}] {ds[r['id'][:4]]['text']['pt'][:70]}")


def main() -> None:
    if "--offline" in sys.argv:
        path, rows = latest_run("04_composite_scoring")
        print(f"offline: {path.name}\n")
        return analyze(rows)

    items = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines()]
    client = JevClient()
    log = RunLog("04_composite_scoring")
    jobs = [(it, lang) for it in items for lang in ("pt", "en")]
    client.decide({"ticket": "warm-up"}, {"blocked": Q["blocked"]})
    with ThreadPoolExecutor(max_workers=8) as ex:
        decisions = list(ex.map(lambda j: client.decide({"ticket": j[0]["text"][j[1]]}, Q), jobs))
    for (it, lang), d in zip(jobs, decisions):
        log.write(f"{it['id']}-{lang}", d, expected=it["labels"], lang=lang, difficulty=it["difficulty"], tags=it["tags"])
    print(f"{len(jobs)} chamadas · ${sum(d.cost or 0 for d in decisions):.5f} · {decisions[-1].model}\nlog: {log.path}\n")
    analyze(latest_run("04_composite_scoring")[1])


if __name__ == "__main__":
    main()
