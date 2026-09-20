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

## Checklist de ops de um ambiente novo

O que o `provision-prd.sh` NÃO faz — convenções do `lab` e segredos que nascem fora do servidor:

| # | O quê | Comando | Por quê |
|---|---|---|---|
| 1 | `GITHUB_TOKEN` nos containers | `scripts/ops/set-github-token.sh` | sem token: 60 req/h por IP no GitHub, somando test + prd (mesmo IP de saída) → ~30 triagens novas/hora no total |
| 2 | Key do OpenRouter dedicada, com limite de crédito | `CONTAINER_NAME=<c> scripts/ops/set-openrouter-key.sh` | é o teto duro de gasto |
| 3 | Conferir drift do inventory | `cd ../lab && tools/sync-inventory.sh` | o `request-flow` do lab só fecha a instalação depois disso |
| 4 | DNS de fallback | `cd ../lab && bash tools/deploy-dns.sh` | `docs/dns.md`: domínio novo → regenerar; é o que o Uptime Kuma e containers fora da tailnet usam pra resolver |
| 5 | Monitor no Uptime Kuma | `gen-monitoring-configs.py` + `apply-monitoring-config.py` (pede credenciais do Kuma e do Telegram) | ADR-0001 do lab: app público sem monitor cai em silêncio |
| 6 | Segredos no Vaultwarden | itens `jev-o-matic-<env> OPENROUTER_API_KEY` / `GITHUB_TOKEN` | convenção do lab; key do OpenRouter não é recuperável depois de criada (perdeu → gera outra) |

Nunca use `push-env.sh` num ambiente que já tem key: ele reescreve o `.env` inteiro a partir do Mac (agora exige `--force`).

## Guardas (app pública com a key do dono)

Em memória, por processo: rate limit por IP, teto diário de LLM e de gasto, cache de 10 min por PR. Variáveis e defaults no `.env.example`. Reiniciar zera contadores — o teto duro é o **limite de crédito da key** no OpenRouter.

O rate limit usa o IP que o uvicorn resolve do `X-Forwarded-For`. No vhost público, o Nginx deve **sobrescrever** o header (`proxy_set_header X-Forwarded-For $remote_addr;`), não anexar (`$proxy_add_x_forwarded_for`) — senão o visitante forja o próprio IP. No `-test` (proxy TCP da Tailscale, sem header) todos os visitantes contam como um IP só.

## Atualizar

```bash
scripts/ops/deploy-test.sh    # git pull + compose up --build + health, por SSH (enquanto o CD não está ativo)
```

## Verificar

```bash
curl -fsS http://100.66.254.24:3770/api/health
```

## Voltar atrás

`git checkout <sha-anterior>` em `/opt/app` + `docker compose up -d --build`, ou restaurar o snapshot `deploy-<timestamp>` que o install cria.

## Produção pública — `https://jev-o-matic.oute.pro`

```bash
scripts/ops/provision-prd.sh              # reaproveita o .env do -test (mesma key, mesmo limite de crédito)
scripts/ops/provision-prd.sh --new-key    # pede uma key dedicada ao prd
```

Molde: `studio/scripts/ops/provision-studio-prd.sh`, sem Firebase, banco nem backup. Idempotente. Faz: `install-app --name jev-o-matic-prd --public` → `.env` → stack + health → vhost Nginx + Certbot → verificação (HTTPS, 301, página, triagem real) → vhost, cert e porta 80 no inventory do lab + `PORTS.md`.

- Domínio pela convenção do install-app (`<app>.oute.pro`); `*.oute.pro` já é wildcard no DNS público e no split DNS.
- O vhost **sobrescreve** `X-Forwarded-For` com `$remote_addr` (ver Guardas) e limita o corpo a 16k.
- Pede a senha sudo do host (keychain `lab-oute-sudo` ou digitada) só no passo do Nginx.

Atualizar o prd (o CD só cobre o `-test`; produção é sempre um ato deliberado):

```bash
scripts/ops/deploy-prd.sh     # checkout do SHA da main + rebuild + health + smoke
```

## Smoke

```bash
scripts/ops/smoke.sh          # prd
scripts/ops/smoke.sh test
```

Health, página, 301, uma triagem real conferida contra o contrato, 422 pra URL fora do GitHub, e o IP que a api registrou vs o seu IP público (é o que prova que o rate limit por IP vale no prd). Não gasta LLM. Na tailnet o split DNS leva ao IP Tailscale do host: pra conferir o IP de visitante, rode de fora (4G).
