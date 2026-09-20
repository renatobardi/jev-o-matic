#!/usr/bin/env bash
# Smoke pós-deploy (issue #37). Roda no Mac. Não gasta LLM de propósito: usa um PR que o jev
# resolve sozinho (tradução de docs).
#
#   scripts/ops/smoke.sh          # prd  — https://jev-o-matic.oute.pro
#   scripts/ops/smoke.sh test     # test — http://100.66.254.24:3770 (Tailscale)
set -euo pipefail

ENVIRONMENT="${1:-prd}"
HOST="${OUTE_HOST:-oute-server}"
case "${ENVIRONMENT}" in
    prd)  URL="https://jev-o-matic.oute.pro"; NAME="jev-o-matic-prd" ;;
    test) URL="http://100.66.254.24:3770";    NAME="jev-o-matic-test" ;;
    *) echo "uso: smoke.sh [prd|test]" >&2; exit 2 ;;
esac
PR="https://github.com/fastapi/fastapi/pull/13000"
fail() { echo "FAIL: $1" >&2; exit 1; }

echo "==> ${ENVIRONMENT}: ${URL}"
health="$(curl -fsS --max-time 15 "${URL}/api/health")" || fail "/api/health"
echo "    health: ${health}"
curl -fsS --max-time 15 "${URL}/" | grep -q '<div id="root">' || fail "página"
echo "    página OK"
if [[ "${ENVIRONMENT}" == "prd" ]]; then
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "http://jev-o-matic.oute.pro/")"
    [[ "${code}" == "301" ]] || fail "http:// devolveu ${code}, esperado 301"
    echo "    http -> https OK"
fi

body="$(curl -fsS --max-time 60 -X POST "${URL}/api/triage" -H 'Content-Type: application/json' \
    -d "{\"url\":\"${PR}\"}")" || fail "POST /api/triage"
printf '%s' "${body}" | python3 -c '
import json, sys
d = json.load(sys.stdin)
need = {"pr", "decisions", "verdict", "sent", "trace", "versions", "categories", "cached"}
missing = need - set(d)
assert not missing, f"schema sem {missing}"
assert d["verdict"]["lane"] in ("fast", "normal", "senior"), d["verdict"]
assert [s["stage"] for s in d["trace"]] == ["github", "jev", "code", "llm"], d["trace"]
jev, v, ver = d["trace"][1], d["verdict"], d["versions"]
ms = round(jev["latency_ms"])
# sem aspas escapadas dentro de f-string: o python3 do macOS pode ser < 3.12
print("    triagem: via=%s · jev %d ms · cache=%s · %s · perguntas %s"
      % (v["lane"], ms, d["cached"], ver["jev_model"], ver["questions"]))
' || fail "resposta da triagem fora do contrato"

bad="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST "${URL}/api/triage" \
    -H 'Content-Type: application/json' -d '{"url":"https://evil.example/o/r/pull/1"}')"
[[ "${bad}" == "422" ]] || fail "URL fora do GitHub devolveu ${bad}, esperado 422"
echo "    URL fora do GitHub -> 422 OK"

# O rate limit é por IP. No prd o IP tem que ser o do VISITANTE (Nginx sobrescreve X-Forwarded-For);
# se aparecer 10.173.117.1 ou 172.x, todo mundo está contando como um IP só.
seen="$(ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app && docker compose logs --no-color --tail 40 api'" \
    | grep 'POST /api/triage' | tail -1 | grep -oE '[0-9]{1,3}(\.[0-9]{1,3}){3}' | head -1 || true)"
mine="$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || true)"
echo "    IP que a api registrou: ${seen:-?} · seu IP público: ${mine:-?}"
if [[ "${ENVIRONMENT}" == "prd" && -n "${seen}" && -n "${mine}" && "${seen}" != "${mine}" ]]; then
    echo "    ATENÇÃO: a api não está vendo o IP do visitante — rate limit por IP não vale no prd." >&2
    echo "    (se você está na tailnet, o split DNS leva ao IP Tailscale do host: teste de fora, ex. 4G)" >&2
fi
echo "OK"
