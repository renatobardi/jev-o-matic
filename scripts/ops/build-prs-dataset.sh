#!/usr/bin/env bash
# Lab 09 (#39): monta datasets/prs_v1.jsonl DENTRO do container da api no test (lá tem GITHUB_TOKEN:
# ~120 chamadas, acima do limite anônimo de 60/h). Só GitHub — não chama jev nem LLM, custo zero.
# Não sobrescreve um dataset existente: dataset versionado é congelado; mudou a lista → prs_v2.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAME="${CONTAINER_NAME:-jev-o-matic-test}"
HOST="${INSTALL_APP_HOST:-oute-server}"
OUT="${ROOT}/datasets/prs_v1.jsonl"

if [[ -s "${OUT}" && "${1:-}" != "--force" ]]; then
    echo "erro: ${OUT} já existe (dataset congelado). --force só se ele ainda não foi usado em nenhum run." >&2
    exit 1
fi

trap 'rm -f "${OUT}.tmp"' EXIT

echo "==> test na main (o script usa o state.py atual)"
"${ROOT}/scripts/ops/deploy-test.sh"

echo "==> buscando os PRs dentro do ${NAME}"
ssh "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app && docker compose exec -T api python -'" \
    < "${ROOT}/datasets/build_prs.py" > "${OUT}.tmp"
mv "${OUT}.tmp" "${OUT}"

python3 "${ROOT}/datasets/build_prs.py" --stats
echo "ok: ${OUT} ($(du -h "${OUT}" | cut -f1))"
