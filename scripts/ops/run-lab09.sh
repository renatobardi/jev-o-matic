#!/usr/bin/env bash
# Lab 09 (#41), metade ONLINE: roda jev (3×) e LLM (1×) em cima do state congelado de
# datasets/prs_v1.jsonl, DENTRO do container da api no test (key e rede estão lá). Sem GitHub.
# Custo estimado: jev ~US$ 0,04 + LLM ~US$ 0,15. ~8 min. Conta no limite da key do test.
#   scripts/ops/run-lab09.sh            # os 59
#   LAB09_LIMIT=3 scripts/ops/run-lab09.sh   # ensaio
# Usa o código que estiver no test: rode deploy-test.sh antes se mudou questions.py.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAME="${CONTAINER_NAME:-jev-o-matic-test}"
HOST="${INSTALL_APP_HOST:-oute-server}"
DATA="${ROOT}/datasets/prs_v1.jsonl"
OUT="${ROOT}/results/09_pr_triage/$(date -u +%Y%m%dT%H%M%SZ).jsonl"
mkdir -p "$(dirname "${OUT}")"

echo "==> dataset → container"
ssh "${HOST}" "lxc exec ${NAME} -- bash -lc 'cat > /tmp/prs_v1.jsonl'" < "${DATA}"
ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app && docker compose cp /tmp/prs_v1.jsonl api:/tmp/prs_v1.jsonl'"

echo "==> rodando (progresso abaixo)"
ssh "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app && docker compose exec -T -e LAB09_LIMIT=${LAB09_LIMIT:-0} api python -'" \
    < "${ROOT}/labs/09_pr_triage/run.py" > "${OUT}.tmp"
mv "${OUT}.tmp" "${OUT}"

echo "ok: ${OUT} ($(($(wc -l < "${OUT}") - 1)) PRs)"
echo "análise (precisa dos rótulos finais): python3 labs/09_pr_triage/run.py --offline --split train"
