#!/usr/bin/env bash
# Roda o bake-off de LLMs DENTRO do container da api no jev-o-matic-test (é lá que está a key
# dedicada e a rede) e traz o JSON pro results/ local. Nada executa no Mac além do ssh.
# ~84 chamadas de LLM, estimativa < US$ 0,50; conta no limite de crédito da key.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAME="${CONTAINER_NAME:-jev-o-matic-test}"
HOST="${INSTALL_APP_HOST:-oute-server}"
OUT="${ROOT}/results/v2_llm_bakeoff/$(date -u +%Y%m%dT%H%M%SZ).json"
mkdir -p "$(dirname "${OUT}")"

echo "==> garante que o servidor está no commit da main (o script usa o llm.py novo)"
"${ROOT}/scripts/ops/deploy-test.sh"

echo "==> rodando no ${NAME} (alguns minutos; progresso abaixo)"
ssh "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app && docker compose exec -T api python -'" \
    < "${ROOT}/api/scripts/llm_bakeoff.py" > "${OUT}"

echo "==> ${OUT}"
python3 "${ROOT}/api/scripts/llm_bakeoff.py" --analyze "${OUT}"
