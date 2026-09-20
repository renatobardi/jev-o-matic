#!/usr/bin/env bash
# Confere, DE FORA, o que a revisão de segurança assume sobre o prd. Roda no Mac. Não gasta crédito:
# nenhuma chamada chega ao jev (URL inválida, health, cabeçalhos). Sai com 1 se algo falhar.
#   scripts/ops/security-check.sh
set -uo pipefail

DOMAIN="${DOMAIN:-jev-o-matic.oute.pro}"
PUBLIC_IP="${PUBLIC_IP:-140.238.238.118}"
HOST="${OUTE_HOST:-oute-server}"
NAME="${CONTAINER_NAME:-jev-o-matic-prd}"
fail=0
ok()  { echo "  ok    $1"; }
bad() { echo "  FALHA $1" >&2; fail=1; }

echo "==> cabeçalhos de https://${DOMAIN}/"
H="$(curl -fsSI --max-time 15 "https://${DOMAIN}/" | tr -d '\r')"
for h in content-security-policy strict-transport-security x-content-type-options x-frame-options referrer-policy; do
    grep -qi "^${h}:" <<<"${H}" && ok "${h}" || bad "sem ${h}"
done
grep -qi "^content-security-policy:.*script-src 'self'" <<<"${H}" && ok "CSP sem script inline" || bad "CSP não restringe script-src"

echo "==> superfície da API"
[[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://${DOMAIN}/api/docs")" == "404" ]] && ok "/api/docs fechado" || bad "/api/docs publicado"
[[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://${DOMAIN}/api/openapi.json")" == "404" ]] && ok "/api/openapi.json fechado" || bad "openapi publicado"
[[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST "https://${DOMAIN}/api/triage" -H 'Content-Type: application/json' -d '{"url":"http://169.254.169.254/latest/meta-data"}')" == "422" ]] && ok "URL fora do GitHub -> 422 (sem SSRF)" || bad "URL interna não foi recusada com 422"
big="$(python3 -c 'print("{\"url\":\"" + "a"*40000 + "\"}")')"
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST "https://${DOMAIN}/api/triage" -H 'Content-Type: application/json' -d "${big}")"
[[ "${code}" == "413" ]] && ok "corpo de 40 KB -> 413 (limite do Nginx)" || bad "corpo grande devolveu ${code}, esperado 413"

echo "==> o container só é alcançável pelo Nginx do host"
for port in 3780 8000 8080; do
    if nc -z -w 3 "${PUBLIC_IP}" "${port}" 2>/dev/null; then bad "porta ${port} aberta em ${PUBLIC_IP}"; else ok "porta ${port} fechada"; fi
done

echo "==> TLS"
if echo | openssl s_client -connect "${DOMAIN}:443" -servername "${DOMAIN}" -tls1_1 2>/dev/null | grep -q "Cipher is [A-Z0-9]"; then bad "aceita TLS 1.1"; else ok "TLS 1.1 recusado"; fi
exp="$(echo | openssl s_client -connect "${DOMAIN}:443" -servername "${DOMAIN}" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
[[ -n "${exp}" ]] && ok "certificado válido até ${exp}" || bad "não li o certificado"

echo "==> segredos e token no servidor"
perm="$(ssh -n "${HOST}" "lxc exec ${NAME} -- stat -c '%a %U' /opt/app/.env" 2>/dev/null)"
[[ "${perm}" == "600 root" ]] && ok ".env 600 root" || bad ".env com permissão '${perm}' (esperado 600 root)"
# O token NÃO sai do servidor: a chamada é feita lá dentro e só volta um número.
priv="$(ssh "${HOST}" "lxc exec ${NAME} -- bash -s" 2>/dev/null <<'REMOTE'
T="$(grep -m1 '^GITHUB_TOKEN=' /opt/app/.env | cut -d= -f2- | tr -d '[:space:]')"
[ -n "$T" ] || { echo sem-token; exit 0; }
curl -s --max-time 15 -H "Authorization: Bearer $T" "https://api.github.com/user/repos?visibility=private&per_page=1" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else 0)'
REMOTE
)"
case "${priv}" in
    0) ok "GITHUB_TOKEN não enxerga nenhum repo privado" ;;
    sem-token) ok "sem GITHUB_TOKEN (só API anônima)" ;;
    *) bad "GITHUB_TOKEN enxerga repo PRIVADO (${priv:-erro}) — troque por um fine-grained 'Public repositories (read-only)'" ;;
esac

echo
[[ ${fail} -eq 0 ]] && echo "OK: nenhuma falha" || echo "HÁ FALHAS acima" >&2
exit ${fail}
