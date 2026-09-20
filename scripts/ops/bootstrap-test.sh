#!/usr/bin/env bash
# Bootstrap único do jev-o-matic-test no oute-server. Roda no Mac (é quem tem Tailscale SSH e o
# repo `lab`). Idempotente: o install-app é no-op se o app já está no inventory.
#
#   scripts/ops/bootstrap-test.sh            # faz tudo
#   scripts/ops/bootstrap-test.sh --dry-run  # só mostra o plano do install
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAB="${LAB_REPO:-${ROOT}/../lab}"
NAME=jev-o-matic-test
PORT="${APP_PORT:-3770}"
REPO_URL=https://github.com/renatobardi/jev-o-matic
HOST="${INSTALL_APP_HOST:-oute-server}"
INSTALL="${LAB}/.devin/skills/install-app/scripts/install-app.sh"

[[ -x "${INSTALL}" ]] || { echo "erro: não achei o install-app em ${LAB} (defina LAB_REPO)" >&2; exit 2; }
[[ -f "${ROOT}/.env" ]] || { echo "erro: ${ROOT}/.env não existe (copie de .env.example)" >&2; exit 2; }

if [[ "${1:-}" == "--dry-run" ]]; then
    (cd "${LAB}" && "${INSTALL}" "${REPO_URL}" --port "${PORT}" --dry-run)
    exit 0
fi

echo "==> 1/5 main no GitHub (o servidor clona de lá)"
cd "${ROOT}"
[[ "$(git rev-parse main)" == "$(git rev-parse origin/main)" ]] || git push origin main

echo "==> 2/5 install-app (LXC + Docker + clone + compose up) — alguns minutos na primeira vez"
RESUME=()
if ssh -n "${HOST}" "lxc info ${NAME}" >/dev/null 2>&1; then
    # Sobrou de uma tentativa que falhou: o install-app não re-clona um /opt/app que já existe,
    # então o checkout é atualizado aqui antes de retomar.
    echo "    container já existe — atualizando /opt/app e retomando (--resume)"
    ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app 2>/dev/null && git pull --ff-only || true'"
    RESUME=(--resume)
fi
(cd "${LAB}" && "${INSTALL}" "${REPO_URL}" --port "${PORT}" ${RESUME[@]+"${RESUME[@]}"})  # forma segura com `set -u` no bash 3.2 do macOS

echo "==> 3/5 segredos: .env → /opt/app/.env (modo 600; o valor não passa por tela nem argumento)"
{ grep -vE '^(APP_PORT)=' "${ROOT}/.env"; echo "APP_PORT=${PORT}"; } \
    | ssh "${HOST}" "lxc exec ${NAME} -- bash -c 'umask 077 && cat > /opt/app/.env'"

echo "==> 4/5 recria a stack com o .env"
ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app && git pull --ff-only && docker compose up -d --build'"

echo "==> 5/5 health"
TS_IP="$(cd "${LAB}" && python3 tools/inventory_ops.py server-ip servers/oute-server/inventory.yaml)"
for attempt in $(seq 1 30); do
    if curl -fsS --max-time 3 "http://${TS_IP}:${PORT}/api/health"; then
        echo; echo "ok: http://${TS_IP}:${PORT}"
        echo "lembrete: commitar inventory.yaml + PORTS.md no repo lab"
        exit 0
    fi
    sleep 2
done
echo "erro: subiu mas /api/health não respondeu em http://${TS_IP}:${PORT}" >&2
exit 1
