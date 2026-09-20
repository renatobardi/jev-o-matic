#!/usr/bin/env bash
# Provisiona o jev-o-matic-prd em https://jev-o-matic.oute.pro (issue #35), no molde do
# studio/scripts/ops/provision-studio-prd.sh — sem Firebase, banco nem backup: o app não guarda estado.
# Roda no Mac (Tailscale SSH + repo lab). Cada passo é pulado se já feito.
#
#   scripts/ops/provision-prd.sh              # key: copia o /opt/app/.env do -test (dentro do servidor)
#   scripts/ops/provision-prd.sh --new-key    # key: pede uma key dedicada ao prd (colar, sem eco)
#
#   1. install-app.sh --name jev-o-matic-prd --public (repo lab)
#   2. /opt/app/.env no container (segredo nunca em argv, log ou tela)
#   3. sobe a stack e espera o health
#   4. vhost Nginx + Certbot
#   5. verifica HTTPS, http→https, página e uma triagem de ponta a ponta
#   6. registra vhost, cert e a porta 80 no inventory do lab e regenera o PORTS.md
#
# O domínio segue a convenção do install-app (`<app>.oute.pro`). `*.oute.pro` já é wildcard no DNS
# público e no split DNS da tailnet (lab/docs/dns.md): não há registro pra criar.
set -euo pipefail

HOST="${OUTE_HOST:-oute-server}"
NAME=jev-o-matic-prd
TEST_NAME=jev-o-matic-test
DOMAIN=jev-o-matic.oute.pro
PUBLIC_IP=140.238.238.118
TAILSCALE_IP=100.66.254.24
REPO_URL=https://github.com/renatobardi/jev-o-matic
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAB_DIR="${LAB_DIR:-${ROOT}/../lab}"
NEW_KEY=false
[[ "${1:-}" == "--new-key" ]] && NEW_KEY=true

# ---------------------------------------------------------------- pré-checks
for tool in ssh dig curl python3; do
    command -v "${tool}" >/dev/null 2>&1 || { echo "error: ${tool} não encontrado" >&2; exit 2; }
done
[[ -d "${LAB_DIR}" ]] || { echo "error: repo lab não encontrado em ${LAB_DIR} (use LAB_DIR=)" >&2; exit 2; }
# Caminho canônico: o path_utils do lab recusa qualquer caminho com "..".
LAB_DIR="$(cd "${LAB_DIR}" && pwd -P)"
INSTALL="${LAB_DIR}/.devin/skills/install-app/scripts/install-app.sh"
[[ -x "${INSTALL}" ]] || { echo "error: install-app não encontrado em ${LAB_DIR}" >&2; exit 2; }
LAB_PY="${LAB_DIR}/.venv/bin/python"
[[ -x "${LAB_PY}" ]] || LAB_PY=python3
[[ "$(dig +short "${DOMAIN}" @1.1.1.1 | tail -1)" == "${PUBLIC_IP}" ]] \
    || { echo "error: ${DOMAIN} não resolve publicamente para ${PUBLIC_IP}" >&2; exit 2; }
cd "${ROOT}"
git fetch --quiet origin main
[[ "$(git rev-parse main)" == "$(git rev-parse origin/main)" ]] \
    || { echo "error: main local ≠ origin/main — dê push antes (o servidor clona do GitHub)" >&2; exit 2; }

# $1 não pode conter aspas simples: vai dentro de bash -c '...' no container.
on_prd() { ssh -n "${HOST}" "lxc exec ${NAME} -- bash -c 'cd /opt/app && $1'"; }

get_sudo_pass() {
    if command -v security >/dev/null 2>&1 && security find-generic-password -s "lab-oute-sudo" -w >/dev/null 2>&1; then
        security find-generic-password -s "lab-oute-sudo" -w
        return
    fi
    local pass
    read -r -s -p "Senha sudo de ${HOST}: " pass
    echo >&2
    printf '%s\n' "${pass}"
}

# ------------------------------------------------------------- 1. container
if ssh -n "${HOST}" "lxc info ${NAME}" >/dev/null 2>&1; then
    echo "==> 1. ${NAME} já existe"
else
    echo "==> 1. install-app ${NAME} --public (alguns minutos)"
    (cd "${LAB_DIR}" && "${INSTALL}" "${REPO_URL}" --name "${NAME}" --public)
fi
CONTAINER_IP=$(ssh -n "${HOST}" "lxc list ${NAME} -c 4 --format csv" | grep -o '10\.173\.117\.[0-9]* (eth0)' | cut -d' ' -f1 | head -1)
[[ -n "${CONTAINER_IP}" ]] || { echo "error: IP eth0 de ${NAME} não encontrado" >&2; exit 1; }
echo "    ${NAME} em ${CONTAINER_IP}"

# ------------------------------------------------------------------ 2. .env
if on_prd 'test -s .env && grep -q "^OPENROUTER_API_KEY=." .env'; then
    echo "==> 2. .env já tem key — não mexo"
elif ${NEW_KEY}; then
    echo "==> 2. key dedicada ao prd"
    CONTAINER_NAME="${NAME}" "${ROOT}/scripts/ops/set-openrouter-key.sh"
else
    echo "==> 2. copiando o .env do ${TEST_NAME} (de container pra container, dentro do servidor)"
    ssh -n "${HOST}" "lxc exec ${TEST_NAME} -- cat /opt/app/.env | lxc exec ${NAME} -- bash -c 'umask 077; cat > /opt/app/.env'"
    on_prd 'grep -q "^OPENROUTER_API_KEY=." .env' || { echo "FAIL: o .env copiado não tem key" >&2; exit 1; }
    # A porta alocada pro prd no inventory é outra; o Nginx fala com a :80, mas o .env fica coerente.
    PRD_PORT=$("${LAB_PY}" -c "import sys,yaml; inv=yaml.safe_load(open(sys.argv[1])); print(next(c['port'] for c in inv['containers'] if c['name']==sys.argv[2]))" \
        "${LAB_DIR}/servers/oute-server/inventory.yaml" "${NAME}")
    on_prd "sed -i s/^APP_PORT=.*/APP_PORT=${PRD_PORT}/ .env"
    echo "    mesma key (e mesmo limite de crédito) do -test; troque depois com:"
    echo "    CONTAINER_NAME=${NAME} scripts/ops/set-openrouter-key.sh"
fi

# ----------------------------------------------------------------- 3. stack
echo "==> 3. stack no commit da main"
SHA="$(git rev-parse origin/main)"
on_prd "git fetch --quiet origin main && git checkout --force --detach ${SHA} && docker compose up -d --build >/dev/null 2>&1 && docker compose restart caddy >/dev/null 2>&1"
for _ in $(seq 1 60); do on_prd 'curl -fsS -o /dev/null http://localhost/api/health' 2>/dev/null && break; sleep 2; done
on_prd 'curl -fsS -o /dev/null http://localhost/api/health' || { echo "FAIL: api não respondeu em ${NAME}" >&2; exit 1; }
on_prd 'docker compose exec -T api sh -c "test -n \"\$OPENROUTER_API_KEY\""' || { echo "FAIL: api sem OPENROUTER_API_KEY" >&2; exit 1; }
echo "    health ok, key presente, em ${SHA:0:7}"

# ---------------------------------------------------------- 4. Nginx/Certbot
echo "==> 4. vhost ${DOMAIN} -> ${CONTAINER_IP}:80"
SUDO_PASS=$(get_sudo_pass)
[[ -n "${SUDO_PASS}" ]] || { echo "error: sem senha sudo" >&2; exit 2; }
REMOTE_TMP=/tmp/provision-jev-o-matic-prd.remote.sh
ssh "${HOST}" "cat > ${REMOTE_TMP}" <<'REMOTE'
set -euo pipefail
AVAILABLE="/etc/nginx/sites-available/${DOMAIN}"
ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"
if [ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
  mkdir -p /var/www/acme
  certbot certonly --webroot -w /var/www/acme -d "${DOMAIN}" \
    --non-interactive --agree-tos --register-unsafely-without-email
fi
[ ! -f "$AVAILABLE" ] || cp "$AVAILABLE" "${AVAILABLE}.bak.$(date +%Y%m%d-%H%M%S)"
cat > "$AVAILABLE" <<EOF
server {
    server_name ${DOMAIN};

    # A api só recebe {"url": "...", "t": 0.7}: nada legítimo passa de poucos KB.
    client_max_body_size 16k;

    location / {
        proxy_pass http://${UPSTREAM};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        # SOBRESCREVE, não anexa (\$proxy_add_x_forwarded_for): o rate limit da api usa este IP,
        # e anexar deixaria o visitante escolher o próprio.
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_http_version 1.1;
        # Triagem com cascata leva alguns segundos (GitHub + jev + LLM).
        proxy_read_timeout 90;
    }

    listen 0.0.0.0:443 ssl;
    listen ${TAILSCALE_IP}:443 ssl;
    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    listen 0.0.0.0:80;
    server_name ${DOMAIN};
    location ^~ /.well-known/acme-challenge/ { root /var/www/acme; }
    location / { return 301 https://\$host\$request_uri; }
}
EOF
ln -sfn "$AVAILABLE" "$ENABLED"
nginx -t
systemctl reload nginx
REMOTE
if ! printf '%s\n' "${SUDO_PASS}" | ssh "${HOST}" \
    "sudo -S -p '' DOMAIN='${DOMAIN}' UPSTREAM='${CONTAINER_IP}:80' TAILSCALE_IP='${TAILSCALE_IP}' bash ${REMOTE_TMP}"; then
    ssh -n "${HOST}" "rm -f ${REMOTE_TMP}" || true
    echo "FAIL: passo Nginx/Certbot falhou (o vhost anterior, se havia, tem .bak)" >&2
    exit 1
fi
ssh -n "${HOST}" "rm -f ${REMOTE_TMP}"
unset SUDO_PASS

# ---------------------------------------------------------- 5. verificação
echo "==> 5. verificando https://${DOMAIN}"
curl -fsS --max-time 15 "https://${DOMAIN}/api/health" >/dev/null || { echo "FAIL: /api/health" >&2; exit 1; }
echo "    /api/health OK"
curl -fsS --max-time 15 "https://${DOMAIN}/" | grep -q '<div id="root">' || { echo "FAIL: página" >&2; exit 1; }
echo "    página OK"
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "http://${DOMAIN}/")
[[ "${code}" == "301" ]] || { echo "FAIL: http:// devolveu ${code}, esperado 301" >&2; exit 1; }
echo "    http -> https OK"
lane=$(curl -fsS --max-time 60 -X POST "https://${DOMAIN}/api/triage" -H 'Content-Type: application/json' \
    -d '{"url":"https://github.com/fastapi/fastapi/pull/13000"}' \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["verdict"]["lane"], d["versions"]["jev_model"])') \
    || { echo "FAIL: triagem de ponta a ponta" >&2; exit 1; }
echo "    triagem real OK: ${lane}"

# ------------------------------------------------------------- 6. inventory
echo "==> 6. inventory do lab"
"${LAB_PY}" - "${LAB_DIR}" "${NAME}" "${DOMAIN}" "${CONTAINER_IP}" "${TAILSCALE_IP}" <<'PY'
import sys
from pathlib import Path

lab, name, domain, ip, ts_ip = sys.argv[1:6]
sys.path.insert(0, str(Path(lab) / "tools"))
import inventory_ops as ops  # mesmo load/validate/write que o install-app usa

path = Path(lab) / "servers/oute-server/inventory.yaml"
inv = ops.load(path)
changed = False
for c in inv["containers"]:
    if c["name"] == name and 80 not in c.get("extra_ports", []):
        c["extra_ports"] = sorted({*c.get("extra_ports", []), 80})  # o Nginx do host fala com o Caddy na :80
        changed = True
if not any(v["server_name"] == domain for v in inv["vhosts"]):
    inv["vhosts"].append({"server_name": domain, "upstream": f"{ip}:80",
                          "listen": ["0.0.0.0:443 ssl", f"{ts_ip}:443 ssl"],
                          "cert": domain, "default_server": False})
    changed = True
if not any(c["domain"] == domain for c in inv["certs"]):
    inv["certs"].append({"domain": domain, "provider": "certbot", "alt_domains": []})
    inv["certs"].sort(key=lambda c: c["domain"])
    changed = True
if changed:
    ops.validate(inv)
    ops.write(path, inv)
    print("    inventory atualizado (commit no repo lab é seu)")
else:
    print("    inventory já estava completo")
PY
PORTS_TMP="$(mktemp "${LAB_DIR}/servers/oute-server/PORTS.md.XXXXXX")"
"${LAB_PY}" "${LAB_DIR}/tools/gen-ports.py" "${LAB_DIR}/servers/oute-server/inventory.yaml" > "${PORTS_TMP}"
mv "${PORTS_TMP}" "${LAB_DIR}/servers/oute-server/PORTS.md"

echo
echo "OK: ${NAME} no ar em https://${DOMAIN}, SHA ${SHA:0:7}."
echo "Próximos: commit de inventory.yaml + PORTS.md no lab; gh issue close 35."
