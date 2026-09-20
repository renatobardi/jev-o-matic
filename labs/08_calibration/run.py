"""Lab 08 — calibração (offline).
(a) noul: probabilidade prevista vs frequência real de 'sim' por faixa + Brier/ECE.
(b) choice/score: confidence vs acerto por faixa.
(c) hipótese do lab 01: confidence == (pmax − 1/n)/(1 − 1/n)?"""

from harness.analysis import acc, latest_run

NOULS = ["refund_wanted", "churn_threat", "has_bug"]
BINS = [(0, .1), (.1, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.01)]


def main() -> None:
    path, rows = latest_run()
    print(f"run: {path.name}\n\n(a) noul — p previsto vs frequência real de True")
    for q in NOULS:
        pts = [(r["answers"][q]["value"], r["expected"][q]) for r in rows]
        brier = sum((p - y) ** 2 for p, y in pts) / len(pts)
        ece = 0.0
        print(f"  {q}  (Brier {brier:.3f})")
        for lo, hi in BINS:
            b = [(p, y) for p, y in pts if lo <= p < hi]
            if not b:
                continue
            mp, fy = sum(p for p, _ in b) / len(b), sum(y for _, y in b) / len(b)
            ece += len(b) / len(pts) * abs(mp - fy)
            print(f"    p∈[{lo:.1f},{min(hi, 1):.1f}) n={len(b):>3}  p médio {mp:.2f}  real {fy:.2f}")
        print(f"    ECE {ece:.3f}")

    print("\n(b) confidence vs acerto")
    for q in ["department", "urgency"]:
        print(f"  {q}")
        for lo, hi in [(0, .5), (.5, .8), (.8, .95), (.95, 1.01)]:
            b = [r["hits"][q] for r in rows if lo <= r["answers"][q]["confidence"] < hi]
            print(f"    conf∈[{lo:.2f},{min(hi, 1):.2f}) n={len(b):>3}  acc {acc(b):.1%}")

    print("\n(c) confidence nativo vs (pmax − 1/n)/(1 − 1/n)")
    for q in ["department", "urgency"]:
        errs = []
        for r in rows:
            a = r["raw"]["answers"][q]
            probs, n = a["probabilities"], len(a["probabilities"])
            errs.append(abs(a["confidence"] - (max(probs.values()) - 1 / n) / (1 - 1 / n)))
        print(f"  {q} (n={n}): erro abs médio {sum(errs) / len(errs):.4f} · máx {max(errs):.4f}")


if __name__ == "__main__":
    main()
