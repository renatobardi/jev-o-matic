# Deploy no oute-server

Convenções do host: `renatobardi/lab` → `docs/oute-server-app-setup.md`. Este app não guarda estado: sem banco, sem volume, sem backup.

## Forma

- LXC não-privilegiado `jev-o-matic-test` (Tailscale-only), criado pelo `install-app.sh` do `lab`.
- Dentro dele, `/opt/app` é um checkout deste repo rodando o `docker-compose.yml` como está: `api`, `web`, `caddy`.
- O Caddy publica `:80` e `:${APP_PORT}` (default 3770 — a porta alocada no inventory; o proxy LXD da Tailscale conecta nela).
- Acesso: `http://100.66.254.24:<porta>` pela tailnet.

## Instalar (uma vez, do repo `lab`)

```bash
.devin/skills/install-app/scripts/install-app.sh https://github.com/renatobardi/jev-o-matic --port 3770
```

Se o inventory alocar outra porta, grave `APP_PORT=<porta>` no `.env` do servidor.

## Segredos

`/opt/app/.env`, modo 600, nunca no git (ver `.env.example`): `OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `JEV_MODEL`, `LLM_MODEL`, `APP_PORT`. Fonte: Vaultwarden, itens `jev-o-matic-test <NOME>`.

Do Mac, sem o valor passar por tela nem histórico:

```bash
ssh oute-server "lxc exec jev-o-matic-test -- bash -c 'umask 077 && cat > /opt/app/.env'" < .env
ssh oute-server "lxc exec jev-o-matic-test -- bash -lc 'cd /opt/app && docker compose up -d'"
```

## Atualizar

```bash
ssh oute-server "lxc exec jev-o-matic-test -- bash -lc 'cd /opt/app && git pull --ff-only && docker compose up -d --build'"
```

## Verificar

```bash
curl -fsS http://100.66.254.24:3770/api/health
```

## Voltar atrás

`git checkout <sha-anterior>` em `/opt/app` + `docker compose up -d --build`, ou restaurar o snapshot `deploy-<timestamp>` que o install cria.

## Público (depois)

Segundo install com `--name jev-o-matic-prd --public`; vhost Nginx `jev.oute.pro` → `<ip-do-container>:80`, Certbot, `X-Forwarded-Proto https`. Antes disso: rate limit e teto diário (M3).
