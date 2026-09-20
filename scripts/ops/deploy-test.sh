#!/usr/bin/env bash
# Atualiza o jev-o-matic-test pro commit da main no GitHub. Roda no Mac (Tailscale SSH).
# Enquanto o CD não está ativo, é o deploy; depois, é o plano B.
# REF=<branch> sobe uma branch JÁ PUSHADA em vez da main (validar antes do merge). Só no test.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAME="${CONTAINER_NAME:-jev-o-matic-test}"
HOST="${INSTALL_APP_HOST:-oute-server}"
URL="${APP_URL:-http://100.66.254.24:3770}"

REF="${REF:-main}"

cd "${ROOT}"
git fetch --quiet origin "${REF}"
if [[ "${REF}" == "main" && "$(git rev-parse main)" != "$(git rev-parse origin/main)" ]]; then
    echo "==> main local ≠ origin/main — dando push"
    git push origin main
fi
SHA="$(git rev-parse "origin/${REF}")"

echo "==> ${NAME}: checkout de ${SHA:0:7} e rebuild"
ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'set -eu; cd /opt/app; git fetch --quiet origin ${REF}; git checkout --force --detach ${SHA}; docker compose up -d --build 2>&1 | tail -15; docker compose restart caddy'"

echo "==> health"
for attempt in $(seq 1 30); do
    if curl -fsS --max-time 3 2>/dev/null "${URL}/api/health"; then
        echo; echo "ok: ${URL} em ${SHA:0:7}"
        exit 0
    fi
    sleep 2
done
echo "erro: ${URL}/api/health não respondeu" >&2
exit 1
