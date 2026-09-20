# Deploy no oute-server

Convenções do host: `renatobardi/lab` → `docs/oute-server-app-setup.md`. Este app não guarda estado: sem banco, sem volume, sem backup.

## Forma

- LXC não-privilegiado `jev-o-matic-test` (Tailscale-only), criado pelo `install-app.sh` do `lab`.
- Dentro dele, `/opt/app` é um checkout deste repo rodando o `docker-compose.yml` como está: `api`, `web`, `caddy`.
- O Caddy publica `:80` e `:${APP_PORT}` (default 3770 — a porta alocada no inventory; o proxy LXD da Tailscale conecta nela).
- Acesso: `http://100.66.254.24:<porta>` pela tailnet.

## Instalar (uma vez, do Mac — é quem tem Tailscale SSH e o repo `lab`)

```bash
scripts/ops/bootstrap-test.sh --dry-run   # confere o plano
scripts/ops/bootstrap-test.sh             # push, install-app, .env no servidor, compose up, health
```

O script chama o `install-app.sh` do `lab` com `--port 3770`. Depois, commitar `inventory.yaml` + `PORTS.md` no `lab`.

## CD (depois do bootstrap, nada mais roda no Mac além do `git push`)

`.github/workflows/cd.yml`: CI verde na `main` → Tailscale + SSH → checkout do SHA validado em `/opt/app` → `docker compose up -d --build` → health. Segredos do repo, uma vez (mesmos valores que o studio usa pra Tailscale/SSH):

```bash
gh secret set TS_AUTHKEY_DEV       # authkey efêmera da tailnet (Vaultwarden)
gh secret set JEV_CD_SSH_KEY < caminho/da/chave_privada_de_deploy
gh secret set JEV_TEST_SSH_HOST --body 'ubuntu@oute-server'
gh secret set JEV_TEST_URL --body 'http://100.66.254.24:3770'
```

E criar o environment `jev-o-matic-test` no repo (Settings → Environments). Sem os segredos o CD falha no primeiro passo e o deploy manual abaixo continua valendo.

## Segredos

`/opt/app/.env`, modo 600, nunca no git (ver `.env.example`): `OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `JEV_MODEL`, `LLM_MODEL`, `APP_PORT`. Fonte: Vaultwarden, itens `jev-o-matic-test <NOME>`.

Do Mac, sem o valor passar por tela, argumento nem histórico:

```bash
scripts/ops/push-env.sh
```

Cada variável vem do `.env` da raiz; se lá estiver vazia, do ambiente do shell (key exportada no `~/.zshrc`, por exemplo). O script grava o arquivo no container, recria a `api` e confere que a key está presente — sem imprimir valor.

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
