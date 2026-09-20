"""Lab 09 — triagem de PR contra rótulo (épico #38).

RÓTULO: datasets/prs_v1_labels.jsonl foi feito por UM rotulador, o Claude, lendo os diffs às cegas
(sem ver as respostas do jev/LLM). Não é rótulo humano: o Bardi decidiu não rotular (lab simples).
Lição do lab 05 vale aqui: rótulo de LLM tende a favorecer LLM. Atenua: o rotulador é de outra
família que os avaliados (jev, gpt-luna). Ler os números como "concorda com um revisor-IA cuidadoso".

Duas metades, como o lab 00:
  ONLINE  (chama jev e LLM, ~US$ 0,20): roda DENTRO do container da api no test, em cima do state
          congelado de datasets/prs_v1.jsonl — sem GitHub. Use scripts/ops/run-lab09.sh.
          Pra cada PR: 3 runs do jev nas 8 perguntas (estabilidade) + 1 chamada do LLM nas 5
          perguntas que definem a via (baseline "LLM puro"). Com isso a cascata é recalculada
          OFFLINE em qualquer threshold, com o verdict.py de produção.
  OFFLINE (grátis): `uv run lab 09 --offline` ou `python3 labs/09_pr_triage/run.py --offline`.
          Junta o último run com datasets/prs_v1_labels.jsonl e imprime a análise.

Regra do split (lição do lab 04): número que vai pra fora sai do TESTE. O treino existe pra
iterar wording; `--offline --split train` mostra os erros dele, `--split test` só no fim.

Simplificação conhecida: na produção o LLM recebe só as perguntas abaixo de t; aqui recebe sempre
as 5. A resposta a uma pergunta pode variar um pouco com as vizinhas."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

JEV_RUNS = 3
THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9]
LANES = ["fast", "normal", "senior"]
NOULS = [
    "touches_auth_security",
    "touches_data_schema",
    "breaking_api",
    "touches_infra_ci",
    "has_tests",
    "description_explains_why",
]
QUESTION_KEYS = ["change_type", "risk", *NOULS]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ online (no container)


def _ans(a: Any) -> dict[str, Any]:
    return {"value": a.value, "confidence": a.confidence, "probabilities": a.probabilities}


async def _one(
    row: dict[str, Any], questions: dict[str, Any], lane_q: dict[str, Any]
) -> dict[str, Any]:
    from jevomatic_api.jev import decide
    from jevomatic_api.llm import LlmUnavailable, second_opinion

    out: dict[str, Any] = {"id": row["id"], "jev": [], "llm": None}
    for _ in range(JEV_RUNS):
        r = await decide(row["state"], questions)
        out["jev"].append(
            {
                "answers": {k: _ans(a) for k, a in r.answers.items()},
                "latency_ms": r.latency_ms,
                "cost": r.cost,
                "input_tokens": r.input_tokens,
                "model": r.model,
            }
        )
    try:
        op = await second_opinion(row["state"], lane_q)
    except LlmUnavailable as e:
        log(f"  LLM indisponível em {row['id']}: {e}")
        return out
    out["llm"] = {
        "answers": {
            k: {"value": v.answer.value, "rationale": v.rationale} for k, v in op.answers.items()
        },
        "latency_ms": op.latency_ms,
        "cost": op.cost,
        "model": op.model,
    }
    return out


async def online() -> None:
    from jevomatic_api.questions import QUESTIONS, QUESTIONS_VERSION
    from jevomatic_api.verdict import LANE_KEYS

    path = Path(os.getenv("PRS_DATASET", "/tmp/prs_v1.jsonl"))
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    rows = rows[: int(os.getenv("LAB09_LIMIT", "0")) or len(rows)]  # LAB09_LIMIT=3 pra ensaio
    lane_q = {k: QUESTIONS[k] for k in LANE_KEYS}
    print(
        json.dumps({"meta": {"questions": QUESTIONS_VERSION, "jev_runs": JEV_RUNS, "n": len(rows)}})
    )
    for i, row in enumerate(rows, 1):
        try:
            res = await _one(row, QUESTIONS, lane_q)
        except Exception as e:  # noqa: BLE001 — registra e segue
            log(f"✗ {row['id']} {row['slug']}: {e!r}")
            continue
        print(json.dumps(res, ensure_ascii=False), flush=True)
        log(f"✓ {i}/{len(rows)} {row['id']} {row['slug']}")


# ------------------------------------------------------------------ offline (no Mac, python puro)


def _root() -> Path:
    """Só a metade offline tem arquivo: a online chega por stdin, onde __file__ não é um caminho."""
    return Path(__file__).resolve().parents[2]


def _verdict_fn() -> Any:
    """verdict.py de produção, importado pelo caminho (só stdlib) — sem instalar o pacote."""
    sys.path.insert(0, str(_root() / "api" / "src" / "jevomatic_api"))
    import verdict as v  # type: ignore[import-not-found]

    return v


def _load(split: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    runs = sorted((_root() / "results" / "09_pr_triage").glob("*.jsonl"))
    if not runs:
        sys.exit("nenhum run em results/09_pr_triage/ — rode scripts/ops/run-lab09.sh")
    lines = [json.loads(x) for x in runs[-1].read_text(encoding="utf-8").splitlines() if x.strip()]
    meta, res = lines[0]["meta"], {x["id"]: x for x in lines[1:]}
    labels_path = _root() / "datasets" / "prs_v1_labels.jsonl"
    if not labels_path.exists():
        sys.exit("faltam os rótulos finais: datasets/prs_v1_labels.jsonl (#40)")
    labels = {
        x["id"]: x for x in map(json.loads, labels_path.read_text(encoding="utf-8").splitlines())
    }
    data = [
        json.loads(x)
        for x in (_root() / "datasets" / "prs_v1.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    items = [
        {"pr": d, "label": labels[d["id"]], "run": res[d["id"]]}
        for d in data
        if d["id"] in labels and d["id"] in res and split in ("all", d["split"])
    ]
    meta.update(run=runs[-1].name, split=split)
    return meta, items


def hit(key: str, value: Any, label: dict[str, Any]) -> bool:
    if key == "change_type":
        return bool(value == label[key])
    if key == "risk":
        return bool(round(value) == label[key])
    return bool((value >= 0.5) == label[key])


def _ns(answers: dict[str, Any]) -> dict[str, Any]:
    return {k: SimpleNamespace(**a) for k, a in answers.items()}


def lanes_for(item: dict[str, Any], t: float, v: Any) -> dict[str, Any]:
    """Vias de um PR em t: jev sozinho, cascata (produção), LLM puro e a regra aplicada ao rótulo."""
    pr, run, label = item["pr"], item["run"], item["label"]
    files, runtime = pr["files_changed"], pr["runtime_files"]
    jev = _ns(run["jev"][0]["answers"])
    first = v.verdict(jev, files, t, runtime)
    llm = (run["llm"] or {}).get("answers", {})
    asked = [k for k in v.LANE_KEYS if jev[k].confidence < t] if first.uncertain and llm else []
    casc = dict(jev)
    for k in asked:
        if k in llm:
            casc[k] = SimpleNamespace(value=llm[k]["value"], confidence=1.0, probabilities=None)
    pure = {
        **jev,
        **{
            k: SimpleNamespace(value=a["value"], confidence=1.0, probabilities=None)
            for k, a in llm.items()
        },
    }
    truth = {
        k: SimpleNamespace(value=_label_value(k, label), confidence=1.0, probabilities=None)
        for k in v.LANE_KEYS
    }
    return {
        "jev": first.lane,
        "cascade": v.verdict(casc, files, t, runtime).lane,
        "llm": v.verdict(pure, files, t, runtime).lane if llm else None,
        "rule_on_labels": v.verdict(truth, files, t, runtime).lane,
        "llm_called": bool(asked),
    }


def _label_value(key: str, label: dict[str, Any]) -> Any:
    raw = label[key]
    return float(raw) if isinstance(raw, bool) else raw


def report_questions(items: list[dict[str, Any]]) -> None:
    print("\n== acerto por pergunta (jev, run 1) · cobertura e acerto com confidence ≥ t")
    print(
        f"{'pergunta':<26}{'acerto':>8}"
        + "".join(f"{f'  t={t}':>14}" for t in THRESHOLDS)
        + "   estável 3/3   LLM"
    )
    for key in QUESTION_KEYS:
        rows = [(it["run"]["jev"][0]["answers"][key], it) for it in items]
        hits = [hit(key, a["value"], it["label"]) for a, it in rows]
        cells = []
        for t in THRESHOLDS:
            sel = [h for (a, _), h in zip(rows, hits, strict=True) if a["confidence"] >= t]
            cells.append(f"{sum(sel)}/{len(sel)}".rjust(9) + f" {100 * len(sel) // len(rows):>3}%")
        print(
            f"{key:<26}{sum(hits):>4}/{len(hits):<3}"
            + "".join(cells)
            + f"{_stable(items, key):>11}   {_llm_acc(items, key)}"
        )


def _stable(items: list[dict[str, Any]], key: str) -> str:
    def side(a: dict[str, Any]) -> Any:
        return (
            a["value"]
            if key == "change_type"
            else round(a["value"])
            if key == "risk"
            else a["value"] >= 0.5
        )

    same = sum(1 for it in items if len({side(r["answers"][key]) for r in it["run"]["jev"]}) == 1)
    return f"{same}/{len(items)}"


def _llm_acc(items: list[dict[str, Any]], key: str) -> str:
    got = [
        (it["run"]["llm"]["answers"][key]["value"], it["label"])
        for it in items
        if it["run"]["llm"] and key in it["run"]["llm"]["answers"]
    ]
    return f"{sum(hit(key, val, lab) for val, lab in got)}/{len(got)}" if got else "—"


def report_lanes(items: list[dict[str, Any]], v: Any, t: float) -> None:
    print(
        f"\n== via × a via do rotulador (t={t}) · 'abaixo' = sistema pediu MENOS revisão que o rotulador (o erro caro)"
    )
    rows = [(lanes_for(it, t, v), it["label"]["via"]) for it in items]
    for name in ("jev", "cascade", "llm", "rule_on_labels"):
        pairs = [(r[name], via) for r, via in rows if r[name]]
        ok = sum(a == b for a, b in pairs)
        below = sum(LANES.index(a) < LANES.index(b) for a, b in pairs)
        above = sum(LANES.index(a) > LANES.index(b) for a, b in pairs)
        print(
            f"  {name:<16} igual {ok:>2}/{len(pairs)} · abaixo {below:>2} · acima {above:>2}   {dict(Counter(f'{b}→{a}' for a, b in pairs if a != b))}"
        )
    print(f"  LLM acionado na cascata: {sum(r['llm_called'] for r, _ in rows)}/{len(rows)} PRs")


def report_cost(items: list[dict[str, Any]], v: Any) -> None:
    jev_cost = [it["run"]["jev"][0]["cost"] or 0 for it in items]
    jev_ms = sorted(it["run"]["jev"][0]["latency_ms"] for it in items)
    llm_cost = [(it["run"]["llm"] or {}).get("cost") or 0 for it in items]
    print(
        f"\n== custo · jev US$ {sum(jev_cost):.4f} no total, p50 {jev_ms[len(jev_ms) // 2]:.0f} ms · LLM puro US$ {sum(llm_cost):.4f}"
    )
    for t in THRESHOLDS:
        called = [lanes_for(it, t, v)["llm_called"] for it in items]
        cost = sum(jev_cost) + sum(c for c, used in zip(llm_cost, called, strict=True) if used)
        print(
            f"  t={t}: LLM em {sum(called):>2}/{len(items)} · cascata US$ {cost:.4f} ({100 * cost / max(sum(jev_cost) + sum(llm_cost), 1e-9):.0f}% do jev+LLM sempre)"
        )


def report_errors(items: list[dict[str, Any]], t: float) -> None:
    print(
        f"\n== erros do jev com confidence ≥ {t} (os que a cascata NÃO pega), mais confiantes primeiro"
    )
    errs = []
    for it in items:
        for key in QUESTION_KEYS:
            a = it["run"]["jev"][0]["answers"][key]
            if a["confidence"] >= t and not hit(key, a["value"], it["label"]):
                marks = "".join(
                    m
                    for m, on in (
                        ("?", it["label"].get("duvida")),
                        ("⊘", it["label"].get("fora_do_diff")),
                    )
                    if on
                )
                errs.append(
                    (
                        a["confidence"],
                        f"  {it['pr']['id']} {it['pr']['slug']:<26} {key:<24} jev={a['value']!s:<8} rótulo={it['label'][key]!s:<8} conf={a['confidence']:.2f} {marks}",
                    )
                )
    for _, line in sorted(errs, reverse=True):
        print(line)
    print(
        f"  total {len(errs)} · '?' = rotulador marcou dúvida · '⊘' = só dá pra saber fora do diff"
    )


def offline(split: str) -> None:
    meta, items = _load(split)
    v = _verdict_fn()
    print(
        f"lab 09 · run {meta['run']} · perguntas {meta['questions']} · split={split} · {len(items)} PRs"
    )
    if split != "test":
        print("AVISO: só o split de TESTE gera número pra publicar; treino/all é pra iterar.")
    report_questions(items)
    report_lanes(items, v, v.DEFAULT_T)
    report_cost(items, v)
    report_errors(items, v.DEFAULT_T)


def main() -> None:
    args = sys.argv[1:]
    if "--offline" not in args:
        if Path(os.getenv("PRS_DATASET", "/tmp/prs_v1.jsonl")).exists():
            asyncio.run(online())
            return
        sys.exit(
            "a parte online roda no container do test: scripts/ops/run-lab09.sh · análise: --offline [--split train|test|all]"
        )
    split = args[args.index("--split") + 1] if "--split" in args else "train"
    offline(split)


if __name__ == "__main__":
    main()
