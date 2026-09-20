"""Lab 06 — jaggedness: onde o jev erra e o wording da instrução mitiga?

Alvo: os 2 erros reais do lab 00 (retratação, atribuição a terceiro) + negação simples.
Todas as variantes de instrução vão na MESMA chamada (lab 02: sem drift, custo marginal ~31 tok).

Variantes (churn e bug):
  v0 baseline        instrução usada no lab 00
  v1 scoped_neg      delimita sujeito/tempo usando negações na instrução ("do not count")
  v2 scoped_pos      delimita só com afirmações (sem negação na instrução)
  v3 criteria        instrução curta + criteria true/false explícitos
  v4 decomposed      v0 × (1 − p_retirou) × (1 − p_terceiro), combinado em código
Sondas rápidas das limitações documentadas: contagem e ordenação de datas."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from harness import JevClient, choice, noul
from harness.client import RunLog

from .cases import COUNT, DATES, INTENT

Q = {
    "churn_v0": noul("The customer threatens, announces or requests to cancel, downgrade or leave"),
    "churn_v1": noul("The customer currently intends to cancel or leave OUR service. Intentions that were withdrawn "
                     "do not count. Statements about other companies or other people do not count."),
    "churn_v2": noul("At the end of this message, the author's own current plan is to stop using our service"),
    "churn_v3": noul("The customer intends to cancel or leave",
                     true="The author, speaking for themselves, still wants to cancel, downgrade or leave our service",
                     false="The author stays with us, withdrew an earlier cancellation, is leaving a different company, "
                           "or only mentions someone else cancelling"),
    "bug_v0": noul("The customer reports a software defect or malfunction"),
    "bug_v1": noul("The customer reports a defect in OUR product that affects them now. Defects in other companies' "
                   "products do not count. Statements that there is no bug do not count."),
    "bug_v2": noul("The author is currently experiencing a malfunction in our product"),
    "bug_v3": noul("The customer reports a software defect",
                   true="Our product is malfunctioning for the author right now",
                   false="Everything works, the problem was already fixed, or the defect belongs to another company's product"),
    # peças do v4
    "retracted": noul("The author withdraws, reverses or cancels an earlier request or intention of their own"),
    "about_other": noul("The cancellation or defect mentioned is about another company's product or about another person, not the author's use of our service"),
}
VARIANTS = ["v0", "v1", "v2", "v3", "v4"]

Q_COUNT = {"n_problems": choice("How many distinct problems does the customer report",
                                {"one": "Exactly one problem", "two": "Exactly two problems",
                                 "three": "Exactly three problems", "four_or_more": "Four or more problems"})}
Q_DATES = {"paid_before_due": noul("The payment date is earlier than the due date")}


def p_of(d, target: str, v: str) -> float:
    if v != "v4":
        return d.value(f"{target}_{v}")
    p = d.value(f"{target}_v0") * (1 - d.value("about_other"))
    return p * (1 - d.value("retracted")) if target == "churn" else p


def main() -> None:
    client = JevClient()
    log = RunLog("06_jaggedness")
    client.decide({"ticket": "warm-up"}, Q_DATES)

    with ThreadPoolExecutor(max_workers=8) as ex:
        di = list(ex.map(lambda c: client.decide({"ticket": c[4]}, Q), INTENT))
        dc = list(ex.map(lambda c: client.decide({"ticket": c[2]}, Q_COUNT), COUNT))
        dd = list(ex.map(lambda c: client.decide({"statement": c[2]}, Q_DATES), DATES))

    for c, d in zip(INTENT, di):
        log.write(c[0], d, expected={"churn": c[2], "bug": c[3]}, category=c[1], text=c[4],
                  combined={t: {v: round(p_of(d, t, v), 3) for v in VARIANTS} for t in ("churn", "bug")})
    for c, d in zip(COUNT, dc):
        log.write(c[0], d, expected={"n_problems": c[1]}, category="count", text=c[2])
    for c, d in zip(DATES, dd):
        log.write(c[0], d, expected={"paid_before_due": c[1]}, category="dates", text=c[2])

    cats = ["retraction", "third_party", "negation", "control"]
    for target, idx in (("churn", 2), ("bug", 3)):
        print(f"\n===== {target}: acerto por variante (corte 0.5) · [p médio nos casos False]")
        print(f"{'categoria':13}" + "".join(f"{v:>16}" for v in VARIANTS) + "    n")
        for cat in cats + ["TOTAL"]:
            sel = [(c, d) for c, d in zip(INTENT, di) if (cat == "TOTAL" or c[1] == cat) and c[idx] is not None]
            line = f"{cat:13}"
            for v in VARIANTS:
                ok = sum((p_of(d, target, v) >= .5) == c[idx] for c, d in sel)
                neg = [p_of(d, target, v) for c, d in sel if c[idx] is False]
                pn = f"{sum(neg) / len(neg):.2f}" if neg else " -- "
                line += f"{ok:>6}/{len(sel):<2} [{pn}]"
            print(line + f"   {len(sel):>2}")
        pos = [(c, d) for c, d in zip(INTENT, di) if c[idx] is True]
        print(f"{'recall (True)':13}" + "".join(
            f"{sum(p_of(d, target, v) >= .5 for _, d in pos):>6}/{len(pos):<2} "
            f"[{sum(p_of(d, target, v) for _, d in pos) / len(pos):.2f}]" for v in VARIANTS) + "   [p médio nos True]")

        print(f"\n  erros ({target}):")
        for c, d in zip(INTENT, di):
            if c[idx] is None:
                continue
            ps = {v: p_of(d, target, v) for v in VARIANTS}
            if any((p >= .5) != c[idx] for p in ps.values()):
                print(f"   {c[0]} {c[1]:11} exp={c[idx]!s:5} " + " ".join(f"{v}={p:.2f}{'✗' if (p >= .5) != c[idx] else ' '}" for v, p in ps.items()))

    print("\n===== contagem de problemas")
    for c, d in zip(COUNT, dc):
        a = d.answers["n_problems"]
        print(f"   {c[0]} exp={c[1]:13} got={a['value']:13} conf={a['confidence']:.2f} {'ok' if a['value'] == c[1] else '✗'}")
    print("\n===== ordenação de datas (pagou antes do vencimento?)")
    for c, d in zip(DATES, dd):
        p = d.value("paid_before_due")
        print(f"   {c[0]} exp={c[1]!s:5} p={p:.2f} {'ok' if (p >= .5) == c[1] else '✗'}   {c[2]}")

    cost = sum(d.cost or 0 for d in di + dc + dd)
    print(f"\n{len(di) + len(dc) + len(dd)} chamadas · ${cost:.5f}\nlog: {log.path}")


if __name__ == "__main__":
    main()
