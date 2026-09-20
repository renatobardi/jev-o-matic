#!/usr/bin/env bash
# Grava o GITHUB_TOKEN nos containers do jev-o-matic. Roda no Mac.
#
# Por que importa: sem token a API do GitHub dá 60 requisições/hora POR IP — e test e prd saem
# pelo mesmo IP público do oute-server. Cada triagem nova custa 2 requisições → ~30 triagens/hora
# somando TODOS os visitantes. Com token: 5.000/hora.
#
# Token: github.com/settings/personal-access-tokens → fine-grained, "Public repositories
# (read-only)", sem nenhuma permissão extra. É só leitura de dado público.
#
#   scripts/ops/set-github-token.sh                    # grava em test e prd
#   scripts/ops/set-github-token.sh jev-o-matic-prd    # só num container
#
# O token não é impresso, não entra em argv nem no histórico; só trafega por stdin.
set -euo pipefail

HOST="${OUTE_HOST:-oute-server}"
APP_DIR="${APP_DIR:-/opt/app}"
if [[ $# -gt 0 ]]; then TARGETS=("$@"); else TARGETS=(jev-o-matic-test jev-o-matic-prd); fi

printf 'Cole o token do GitHub (não aparece na tela) e tecle Enter: '
IFS= read -rs TOKEN
echo
TOKEN="$(printf '%s' "${TOKEN}" | tr -d '[:space:]')"
[[ -n "${TOKEN}" ]] || { echo "erro: nada colado" >&2; exit 2; }
case "${TOKEN}" in
    github_pat_*|ghp_*) ;;
    *) echo "erro: não parece token do GitHub (esperado github_pat_… ou ghp_…)" >&2; exit 2 ;;
esac

echo "==> valida o token no GitHub"
INFO="$(printf 'header = "Authorization: Bearer %s"\n' "${TOKEN}" \
    | curl -fsS --max-time 15 -K - -H 'Accept: application/vnd.github+json' https://api.github.com/rate_limit 2>/dev/null)" \
    || { echo "erro: o GitHub recusou o token. Nada foi alterado." >&2; exit 1; }
LIMIT="$(printf '%s' "${INFO}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["resources"]["core"]["limit"])')"
echo "    limite com este token: ${LIMIT} requisições/hora"
[[ "${LIMIT}" -gt 60 ]] || { echo "erro: limite de ${LIMIT}/h — o token não está sendo aceito como autenticado" >&2; exit 1; }

# Sem aspas simples dentro: o bloco vai entre aspas simples pro shell do host não expandir nada.
REMOTE='umask 077; cd "'"${APP_DIR}"'"; touch .env; IFS= read -r tok; { grep -v "^GITHUB_TOKEN=" .env || true; printf "GITHUB_TOKEN=%s\n" "$tok"; } > .env.new; mv .env.new .env; chmod 600 .env'
for NAME in "${TARGETS[@]}"; do
    echo "==> ${NAME}: grava (só a linha do token muda) e recria a api"
    printf '%s\n' "${TOKEN}" | ssh "${HOST}" "lxc exec ${NAME} -- bash -c '${REMOTE}'"
    ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd ${APP_DIR} && docker compose up -d --force-recreate api >/dev/null 2>&1'"
    ssh -n "${HOST}" "lxc exec ${NAME} -- bash -lc 'cd ${APP_DIR} && docker compose exec -T api sh -c \"test -n \\\"\\\$GITHUB_TOKEN\\\" && test -n \\\"\\\$OPENROUTER_API_KEY\\\" && echo \\\"    ok: token e key presentes na api\\\"\"'"
done
unset TOKEN INFO
echo "pronto."
