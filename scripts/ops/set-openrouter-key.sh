#!/usr/bin/env bash
# Troca a OPENROUTER_API_KEY do jev-o-matic-test por uma key dedicada. Roda no Mac.
#
#   scripts/ops/set-openrouter-key.sh          # pede a key (colar; não aparece na tela)
#   scripts/ops/set-openrouter-key.sh --local  # idem, e grava também no .env local (modo 600)
#
# A key nunca é impressa, não entra em argumento de comando (não aparece em `ps` nem no
# histórico) e só trafega por stdin. As outras linhas do .env do servidor são preservadas.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAME="${CONTAINER_NAME:-jev-o-matic-test}"
HOST="${INSTALL_APP_HOST:-oute-server}"
APP_DIR="${APP_DIR:-/opt/app}"
LOCAL=false
[[ "${1:-}" == "--local" ]] && LOCAL=true

printf 'Cole a API key do OpenRouter (não aparece na tela) e tecle Enter: '
IFS= read -rs KEY
echo
KEY="$(printf '%s' "${KEY}" | tr -d '[:space:]')"
[[ -n "${KEY}" ]] || { echo "erro: nada colado" >&2; exit 2; }
[[ "${KEY}" == sk-or-* ]] || { echo "erro: não parece key do OpenRouter (esperado prefixo sk-or-)" >&2; exit 2; }

echo "==> valida a key no OpenRouter"
if INFO="$(printf 'header = "Authorization: Bearer %s"\n' "${KEY}" \
        | curl -fsS --max-time 15 -K - https://openrouter.ai/api/v1/key 2>/dev/null)"; then
    printf '%s' "${INFO}" | python3 -c '
import json, sys
d = json.load(sys.stdin).get("data", {})
limit = d.get("limit")
print("    nome:   ", d.get("label", "?"))
print("    limite: ", "sem limite — defina um no painel do OpenRouter" if limit is None else f"US$ {limit}")
usage = d.get("usage", 0)
print("    usado:  ", f"US$ {usage}")
' || true
else
    echo "erro: o OpenRouter recusou a key (ou está fora do ar). Nada foi alterado." >&2
    exit 1
fi

echo "==> grava em ${NAME}:${APP_DIR}/.env (só a linha da key muda)"
# Sem aspas simples dentro: o bloco vai entre aspas simples pro shell do host não expandir nada.
REMOTE='umask 077; cd "'"${APP_DIR}"'"; touch .env; IFS= read -r key; { grep -v "^OPENROUTER_API_KEY=" .env || true; printf "OPENROUTER_API_KEY=%s\n" "$key"; } > .env.new; mv .env.new .env; chmod 600 .env'
printf '%s\n' "${KEY}" | ssh "${HOST}" "lxc exec ${NAME} -- bash -c '${REMOTE}'"

if ${LOCAL}; then
    echo "==> grava no .env local"
    touch "${ROOT}/.env"
    { grep -v '^OPENROUTER_API_KEY=' "${ROOT}/.env" || true; printf 'OPENROUTER_API_KEY=%s\n' "${KEY}"; } > "${ROOT}/.env.new"
    mv "${ROOT}/.env.new" "${ROOT}/.env"
    chmod 600 "${ROOT}/.env"
fi
unset KEY INFO

echo "==> recria a api"
ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd ${APP_DIR} && docker compose up -d --force-recreate api'"

echo "==> confere dentro do container (só presença e tamanho)"
ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd ${APP_DIR} && docker compose exec -T api sh -c \"test -n \\\"\\\$OPENROUTER_API_KEY\\\" && echo ok: key presente na api, \\\${#OPENROUTER_API_KEY} chars\"'"
echo "pronto. Se a key antiga era só deste projeto, revogue-a no painel do OpenRouter."
