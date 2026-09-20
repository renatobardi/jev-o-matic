"""Lab 03 — roteamento por confidence (offline, sobre o run do lab 00).
Para cada threshold t: cobertura = % decidido automaticamente (conf ≥ t);
acc_auto = acerto nessa fatia; erros_auto = erros que passariam sem revisão."""

from harness.analysis import QUESTIONS, acc, latest_run

THRESHOLDS = [0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]


def main() -> None:
    path, rows = latest_run()
    print(f"run: {path.name} · {len(rows)} decisões por pergunta\n")
    for q in QUESTIONS:
        print(f"{q}")
        print(f"  {'t':>5} {'cobertura':>10} {'acc_auto':>9} {'erros_auto':>11} {'acc_resto':>10}")
        for t in THRESHOLDS:
            auto = [r["hits"][q] for r in rows if r["answers"][q]["confidence"] >= t]
            rest = [r["hits"][q] for r in rows if r["answers"][q]["confidence"] < t]
            print(f"  {t:>5.2f} {len(auto) / len(rows):>10.1%} {acc(auto):>9.1%} "
                  f"{len(auto) - sum(auto):>11} {acc(rest):>10.1%}")
        print()
    # roteamento conjunto: ticket só é automático se TODAS as perguntas-chave passam
    keys = ["department", "refund_wanted", "churn_threat", "has_bug"]
    print("conjunto (department + 3 nouls): automático só se todas ≥ t")
    print(f"  {'t':>5} {'cobertura':>10} {'tickets 100% certos':>20} {'com ≥1 erro':>12}")
    for t in THRESHOLDS:
        auto = [r for r in rows if all(r["answers"][k]["confidence"] >= t for k in keys)]
        ok = sum(all(r["hits"][k] for k in keys) for r in auto)
        print(f"  {t:>5.2f} {len(auto) / len(rows):>10.1%} {ok:>20} {len(auto) - ok:>12}")


if __name__ == "__main__":
    main()
