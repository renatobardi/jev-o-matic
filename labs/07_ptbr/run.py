"""Lab 07 — PT-BR vs EN (offline). Mesmo ticket nos dois idiomas, instruções em inglês."""

from collections import defaultdict

from harness.analysis import QUESTIONS, acc, latest_run


def main() -> None:
    path, rows = latest_run()
    pairs: dict[str, dict] = defaultdict(dict)
    for r in rows:
        pairs[r["id"].split("-")[0]][r["lang"]] = r
    print(f"run: {path.name} · {len(pairs)} pares\n")

    print(f"{'pergunta':15} {'acc PT':>7} {'acc EN':>7} {'conf PT':>8} {'conf EN':>8} {'|Δvalor|':>9} {'discordam':>10}")
    for q in QUESTIONS:
        pt = [p["pt"] for p in pairs.values()]
        en = [p["en"] for p in pairs.values()]
        cpt = sum(r["answers"][q]["confidence"] for r in pt) / len(pt)
        cen = sum(r["answers"][q]["confidence"] for r in en) / len(en)
        if q == "department":
            delta = "-"
            dis = sum(p["pt"]["answers"][q]["value"] != p["en"]["answers"][q]["value"] for p in pairs.values())
        else:
            ds = [abs(p["pt"]["answers"][q]["value"] - p["en"]["answers"][q]["value"]) for p in pairs.values()]
            delta = f"{sum(ds) / len(ds):.3f}"
            if q == "urgency":
                dis = sum(round(p["pt"]["answers"][q]["value"]) != round(p["en"]["answers"][q]["value"]) for p in pairs.values())
            else:
                dis = sum((p["pt"]["answers"][q]["value"] >= .5) != (p["en"]["answers"][q]["value"] >= .5) for p in pairs.values())
        print(f"{q:15} {acc([r['hits'][q] for r in pt]):>7.1%} {acc([r['hits'][q] for r in en]):>7.1%} "
              f"{cpt:>8.3f} {cen:>8.3f} {delta:>9} {dis:>10}")

    lat = {l: sorted(r["latency_ms"] for r in rows if r["lang"] == l) for l in ("pt", "en")}
    tok = {l: sum(r["input_tokens"] for r in rows if r["lang"] == l) for l in ("pt", "en")}
    print(f"\nlatência p50  PT {lat['pt'][len(lat['pt']) // 2]:.0f}ms · EN {lat['en'][len(lat['en']) // 2]:.0f}ms")
    print(f"tokens input  PT {tok['pt']} · EN {tok['en']}  (PT/EN = {tok['pt'] / tok['en']:.3f})")

    print("\npor tag (acc média das 5 perguntas)  PT | EN | n")
    tags = sorted({t for r in rows for t in r["tags"]})
    for t in tags:
        a = {l: [h for r in rows if t in r["tags"] and r["lang"] == l for h in r["hits"].values()] for l in ("pt", "en")}
        print(f"  {t:13} {acc(a['pt']):>6.1%} | {acc(a['en']):>6.1%} | {len(a['pt']) // 5}")


if __name__ == "__main__":
    main()
