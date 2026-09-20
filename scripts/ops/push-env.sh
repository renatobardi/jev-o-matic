#!/usr/bin/env bash
# Grava /opt/app/.env no jev-o-matic-test e recria a api. Roda no Mac.
# Cada variável vem do .env da raiz; se lá estiver vazia, do ambiente do shell (ex.: key exportada
# no ~/.zshrc). Nenhum valor é impresso, nem passa por argumento de comando.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAME="${CONTAINER_NAME:-jev-o-matic-test}"
HOST="${INSTALL_APP_HOST:-oute-server}"
PORT="${APP_PORT:-3770}"
VARS="JEV_BACKEND JEV_MODEL OPENROUTER_API_KEY LLM_MODEL GITHUB_TOKEN"
REQUIRED="OPENROUTER_API_KEY"

from_file() {  # valor de $1 no .env, sem aspas em volta; vazio se ausente
    [[ -f "${ROOT}/.env" ]] || return 0
    sed -n "s/^$1=//p" "${ROOT}/.env" | tail -1 | sed -e 's/[[:space:]]*#.*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

BODY=""
for var in ${VARS}; do
    value="$(from_file "${var}")"
    source_label=".env"
    if [[ -z "${value}" ]]; then
        value="${!var:-}"
        source_label="shell"
    fi
    if [[ -z "${value}" ]]; then
        case " ${REQUIRED} " in
            *" ${var} "*) echo "erro: ${var} vazia no .env e no shell" >&2; exit 2 ;;
        esac
        echo "    ${var}: (não definida — segue sem)"
        continue
    fi
    echo "    ${var}: ok (${source_label}, ${#value} chars)"
    BODY="${BODY}${var}=${value}"$'\n'
done
BODY="${BODY}APP_PORT=${PORT}"$'\n'

printf '%s' "${BODY}" | ssh "${HOST}" "lxc exec ${NAME} -- bash -c 'umask 077 && cat > /opt/app/.env'"
unset BODY value

echo "==> recria a api com o .env novo"
ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app && docker compose up -d --force-recreate api'"

echo "==> confere dentro do container (só presença, nunca o valor)"
ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd /opt/app && docker compose exec -T api sh -c \"test -n \\\"\\\$OPENROUTER_API_KEY\\\" && echo OPENROUTER_API_KEY presente na api\"'"
