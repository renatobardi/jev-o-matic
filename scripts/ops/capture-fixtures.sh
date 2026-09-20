#!/usr/bin/env bash
# Regrava web/src/lib/fixtures.json (?fixture=fast|senior|uncertain|cascade) com respostas REAIS do
# ambiente test. Rodar depois de mudar QUESTIONS_VERSION ou o contrato. 3 triagens, ~1 chamada de LLM.
# `uncertain` (LLM indisponível) não dá pra provocar de fora: é DERIVADO da resposta `cascade`,
# desfazendo o que o LLM respondeu — mesmas respostas do jev, veredito do jev sozinho.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
URL="${APP_URL:-http://100.66.254.24:3770}"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

fetch() { # nome, url do PR
    echo "==> $1 ← $2"
    curl -fsS --max-time 60 -H 'content-type: application/json' \
        -d "{\"url\":\"$2\"}" "${URL}/api/triage" > "${TMP}/$1.json"
}
fetch fast https://github.com/fastapi/fastapi/pull/13000
fetch senior https://github.com/pydantic/pydantic/pull/720
fetch cascade https://github.com/pallets/werkzeug/pull/3252

python3 - "${TMP}" "${ROOT}/web/src/lib/fixtures.json" <<'PYEOF'
import copy, json, sys
from pathlib import Path

tmp, dest = Path(sys.argv[1]), Path(sys.argv[2])
old = json.loads(dest.read_text(encoding="utf-8"))
new = {k: json.loads((tmp / f"{k}.json").read_text(encoding="utf-8")) for k in ("fast", "senior", "cascade")}
for name in ("fast", "senior"):
    got = new[name]["verdict"]["lane"]
    if got != name:
        sys.exit(f"erro: fixture {name} veio com via={got}; nada gravado")
casc = new["cascade"]
if not casc["verdict"]["escalated"]:
    print("aviso: o werkzeug não escalou pro LLM nesta rodada; cascade/uncertain ficam como estavam")
    new["cascade"], new["uncertain"] = old["cascade"], old["uncertain"]
else:
    unc = copy.deepcopy(casc)
    for d in unc["decisions"].values():
        if d.get("original"):
            d.update(d["original"], source="jev", rationale=None, original=None)
    order = ["touches_auth_security", "touches_data_schema", "breaking_api", "risk", "change_type"]
    unc["verdict"].update(
        lane=casc["verdict"]["jev_lane"],
        reasons=["uncertain_decisions"],
        uncertain=sorted(casc["verdict"]["escalated"], key=order.index),
        escalated=[],
    )
    llm = next(s for s in unc["trace"] if s["stage"] == "llm")
    llm.update(latency_ms=0.0, cost=None, input_tokens=None, output_tokens=None, skipped=True,
               note="LLM indisponível — mantido o veredito do jev")
    unc["versions"]["llm_model"] = None
    new["uncertain"] = unc
out = {k: new[k] for k in ("fast", "senior", "uncertain", "cascade")}
dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for k, v in out.items():
    print(f"  {k:<10} {v['pr']['slug']:<28} via={v['verdict']['lane']:<7} perguntas={v['versions']['questions']}")
PYEOF
echo "ok: ${ROOT}/web/src/lib/fixtures.json — revise o diff e commite"
