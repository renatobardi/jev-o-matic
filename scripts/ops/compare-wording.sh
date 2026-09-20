#!/usr/bin/env bash
# Critério de aceite de um wording novo (#12): sobe uma branch no jev-o-matic-test, roda o jev nos
# 14 PRs do bake-off DENTRO do container (é lá que estão a key e a rede) e compara com as respostas
# do wording antigo guardadas em results/v2_llm_bakeoff/. Só jev, sem LLM: < US$ 0,01.
#   REF=feat/questions-pr-v2 scripts/ops/compare-wording.sh
# O test fica na branch até o próximo deploy-test.sh (que volta pra main).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAME="${CONTAINER_NAME:-jev-o-matic-test}"
HOST="${INSTALL_APP_HOST:-oute-server}"
REF="${REF:?uso: REF=<branch já pushada> scripts/ops/compare-wording.sh}"
BASE="$(ls -1 "${ROOT}"/results/v2_llm_bakeoff/*.json | tail -1)"
OUT="${ROOT}/results/v2_wording/$(date -u +%Y%m%dT%H%M%SZ)-${REF//\//_}.json"
mkdir -p "$(dirname "${OUT}")"

echo "==> test ← ${REF}"
REF="${REF}" "${ROOT}/scripts/ops/deploy-test.sh"

echo "==> jev nos 14 PRs, dentro do ${NAME}"
ssh "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app && docker compose exec -T api python -'" \
    < "${ROOT}/api/scripts/wording_compare.py" > "${OUT}"

echo "==> ${OUT}  (base: ${BASE##*/})"
python3 "${ROOT}/api/scripts/wording_compare.py" --analyze "${OUT}" "${BASE}"
