#!/usr/bin/env python3
"""Cria épicos → issues → sub-issues do jev-o-matic v2 (PR Triage) no GitHub.

Requer `gh` autenticado com escrita no repo. Idempotente: issue com o mesmo título é reaproveitada.
  python3 scripts/ops/create_v2_issues.py --dry-run   # só mostra a árvore
  python3 scripts/ops/create_v2_issues.py             # cria
Plano: Project claude.ai "jev-o-matic", doc 10-v2-pr-triage-plano.md
"""

from __future__ import annotations

import json
import subprocess
import sys

REPO = "renatobardi/jev-o-matic"
AGENT, HUMAN = "ready-for-agent", "ready-for-human"
LABELS = {
    "epic": ("5319e7", "Agrupa issues de um marco"),
    "v2": ("0e8a16", "jev-o-matic v2 — PR Triage"),
    AGENT: ("1d76db", "Especificado, pode ser executado por agente"),
    HUMAN: ("d93f0b", "Precisa de ação do Bardi (credencial, servidor, decisão)"),
}


def I(title: str, body: str, who: str = AGENT, subs: list | None = None) -> dict:  # noqa: E743
    return {"title": title, "body": body.strip(), "labels": ["v2", who], "subs": subs or []}


def E(title: str, body: str, subs: list) -> dict:
    return {"title": title, "body": body.strip(), "labels": ["v2", "epic"], "subs": subs}


TREE = [
    E("[Épico] M1 — API de triagem", """
Marco 1: `POST /api/triage` recebe a URL de um PR público e devolve decisões do jev + veredito.
**Feito quando:** um script roda 5 PRs reais e imprime veredito, decisões, confidence, latência e custo.
Stack = studio: FastAPI, uvicorn, Python 3.12, uv + uv_build, ruff, mypy strict, pytest, httpx.
""", [
        I("api: scaffold do projeto", """
Criar `api/` como projeto uv próprio, no padrão do `studio/api`.
- `pyproject.toml` (fastapi, uvicorn[standard], pydantic, httpx, openrouter; dev: pytest, pytest-asyncio, mypy, ruff), `uv.lock`, `.python-version` 3.12
- `src/jevomatic_api/main.py` com `GET /api/health`
- ruff line-length 100, mypy strict, pytest asyncio_mode=auto
- `Dockerfile`: python:3.12-slim, uv pinado, `uv sync --locked`, non-root uid 10001, uvicorn :8000
**Feito quando:** `uv run pytest`, `ruff check`, `mypy` passam e o container responde `/api/health`.
"""),
        I("api: cliente GitHub (URL → PR + arquivos)", """
Módulo `github.py`: transforma a URL colada em dados do PR via GitHub REST. A API só fala com `api.github.com`.
**Feito quando:** dado um PR público, retorna título, descrição, labels, autor, head sha, e lista de arquivos com status, +/−, patch.
""", subs=[
            I("github: parser e validação da URL do PR", """
Aceitar só `https://github.com/{owner}/{repo}/pull/{number}` (com/sem sufixo `/files`, query, fragmento). Rejeitar todo o resto com erro 422 claro. Nunca fazer request pra host vindo do usuário (sem SSRF).
**Feito quando:** testes cobrem URLs válidas, host errado, caminho errado, número não numérico, owner/repo com caracteres inválidos.
"""),
            I("github: fetch do PR e dos arquivos, com erros tratados", """
`GET /repos/{o}/{r}/pulls/{n}` + `/files` paginado (teto de 300 arquivos). Token opcional via `GITHUB_TOKEN`. Timeout 10 s.
Mapear: 404/privado → "PR não encontrado ou privado"; 403 rate limit → 429 com reset; 5xx → 502.
**Feito quando:** testes com respostas simuladas (httpx MockTransport) cobrem sucesso, paginação e cada erro.
"""),
        ]),
        I("api: montagem do state com orçamento de tokens", """
Módulo `state.py`: monta o `state` enviado ao jev dentro de ~20k tokens (ctx = 32k). Estimar tokens por `len/4`.
**Feito quando:** PR grande nunca estoura o orçamento e a resposta diz exatamente o que entrou e o que ficou de fora.
""", subs=[
            I("state: filtro de arquivos sem valor de revisão", """
Descartar patch (manter só nome e +/−) de: lockfiles, `dist/`, `build/`, `vendor/`, `node_modules/`, minificados, snapshots, binários, arquivos gerados (`*.pb.go`, `*_generated.*`, `*.min.*`).
**Feito quando:** lista de padrões testada; arquivo descartado aparece em `omitted` com motivo.
"""),
            I("state: priorização por caminho de risco e truncamento de patch", """
Ordenar arquivos: auth/security/crypto/permission → migrations/schema → API pública/rotas → infra/CI → resto → testes/docs. Incluir patches nessa ordem até o orçamento; patch individual truncado em N linhas com marcador.
**Feito quando:** testes mostram ordem determinística e orçamento respeitado.
"""),
            I("state: relatório de incluídos e omitidos", """
Resposta traz `sent: {tokens_est, files_included[], files_truncated[], files_omitted[{path, reason}]}`.
**Feito quando:** campo presente no schema e coberto por teste.
"""),
        ]),
        I("api: cliente jev e perguntas v1", """
Módulo `jev.py` + `questions.py`. 1 chamada por PR (fan-out é grátis — lab 02).
**Feito quando:** dado um state, retorna as decisões normalizadas (value, confidence, probabilities), latência, tokens e custo.
""", subs=[
            I("jev: cliente mínimo, normalização e backend mock", """
Cópia mínima de `harness/client.py` (decide + normalize + mock), sem RunLog. Backend por env (`JEV_BACKEND=openrouter|mock`), modelo por `JEV_MODEL`. Noul sem confidence nativo → `|p−0,5|×2`. Timeout e 1 retry.
Decisão registrada: duplicar ~60 linhas em vez de depender do `harness/` da raiz (contexto de build = `./api`).
**Feito quando:** testes rodam com mock, sem rede.
"""),
            I("jev: wording das perguntas de PR", """
`change_type` (choice: feature, bugfix, refactor, deps, docs, config_infra, tests_only) · `risk` (score 3 níveis, critérios ancorados em estado observável, mutuamente exclusivos — lab 04 u1) · nouls: `touches_auth_security`, `touches_data_schema`, `breaking_api`, `touches_infra_ci`, `has_tests`, `description_explains_why`.
Regras dos labs: escopar ("o diff MODIFICA lógica de…", não "menciona"); `criteria` true/false com os quase-positivos no false (ex.: arquivo chamado `auth_test.py`, comentário citando "password"); relação dentro de uma pergunta só. Contagem/tamanho fica em código.
**Feito quando:** perguntas versionadas (`QUESTIONS_VERSION`) e revisadas pelo Bardi.
"""),
        ]),
        I("api: veredito determinístico", """
Módulo `verdict.py`, função pura `verdict(decisions, size, t) -> {lane, reasons[], uncertain[]}`.
- `senior`: security | schema | breaking com p ≥ 0,5 e conf ≥ t, ou `risk` nível 2
- `fast`: change_type ∈ {docs, tests_only, deps} com conf ≥ t, nenhum flag acima, PR pequeno
- senão `normal`
- `uncertain`: decisões que definem a lane com conf < t
Regra pequena de propósito (lab 04: compor muitos átomos multiplica falso positivo).
**Feito quando:** tabela de casos em teste, incluindo fronteiras de t.
"""),
        I("api: endpoint POST /api/triage e schema de resposta", """
Entrada `{url}`. Saída: `pr{...}`, `decisions{...}`, `verdict{...}`, `sent{...}`, `trace[{stage, latency_ms, cost, tokens}]`, `versions{questions, model}`. Modelos pydantic; erros no formato `{error:{code,message}}`.
**Feito quando:** teste de integração com GitHub simulado + jev mock devolve o schema completo.
"""),
        I("api: script de smoke com 5 PRs reais", """
`scripts/smoke_prs.py`: chama a API local com 5 PRs públicos variados (docs, deps bump, feature grande, fix de segurança, refactor) e imprime tabela.
**Feito quando:** Bardi roda no Mac (o ambiente do Cowork não alcança openrouter.ai) e cola a saída.
""", who=HUMAN),
    ]),
    E("[Épico] M2 — Web", """
Marco 2: página única que mostra o resultado de um PR.
**Feito quando:** colar uma URL no browser mostra veredito, decisões e o que foi enviado.
Stack = studio: React 19, Vite, TypeScript, bun, oxlint, CSS puro com tokens, nginx-unprivileged :8080. Sem PWA, sem router, sem lib de UI.
""", [
        I("web: scaffold do projeto", """
`web/` com Vite + React 19 + TS, bun, oxlint, `tsc -b`. `styles/tokens/{colors,typography,radius}.css` + `app.css` (claro e escuro). `Dockerfile` (oven/bun build → nginxinc/nginx-unprivileged) e `nginx.conf` (index sem cache, `/assets/` imutável). Proxy de dev do Vite: `/api` → :8000.
**Feito quando:** `bun run build`, `bun run lint` passam e o container serve a página.
"""),
        I("web: formulário de URL, exemplos e estados", """
Campo de URL + botão; 4–5 PRs de exemplo clicáveis; estados vazio, carregando, erro (mensagem da API), sucesso. Validação leve no cliente; a API é a autoridade.
**Feito quando:** os 4 estados renderizam e erro 422/429/502 mostra mensagem legível.
"""),
        I("web: cartão de resultado — selo e decisões com confidence", """
Selo da lane (fast / normal / senior) com os motivos. Lista de decisões: valor, barra de confidence, probabilidades do choice/score em tooltip ou linha secundária. Decisão abaixo do threshold marcada como "incerta".
**Feito quando:** renderiza a partir de um JSON de exemplo fixo (fixture) sem API.
"""),
        I("web: trilha jev → código → LLM com latência e custo", """
Três etapas em sequência com latência, custo e tokens de cada uma; etapa LLM aparece como "não acionada" quando não houve escalonamento. Total no fim, com comparação "se fosse tudo no LLM" quando houver dado.
**Feito quando:** renderiza os dois casos (com e sem LLM) a partir de fixtures.
"""),
        I("web: painel \"o que foi enviado\"", """
Tokens estimados, arquivos incluídos, truncados e omitidos com motivo. Recolhido por padrão.
**Feito quando:** PR grande de exemplo mostra omitidos com motivo.
"""),
        I("web: aviso de demo e rodapé", """
Aviso fixo: demo de laboratório, sem acurácia medida, não usar como gate real. Rodapé: link do repo, versão das perguntas, modelo.
**Feito quando:** visível em todas as telas, claro e escuro.
"""),
    ]),
    E("[Épico] M3 — Cascata LLM e guardas", """
Marco 3: o funil completo (jev → código → LLM) e as proteções de uma app pública rodando com a key do Bardi.
**Feito quando:** PR incerto aciona o LLM, PR óbvio não; abuso é contido por rate limit e teto diário.
""", [
        I("api: cliente LLM — segunda opinião com justificativa", """
`llm.py`: OpenRouter chat completions via httpx (padrão do lab 05: JSON, retry tirando parâmetro não suportado, corpo do erro visível). Entrada: o mesmo state + só as decisões incertas. Saída: valor por decisão + justificativa de 1–2 frases. Modelo por `LLM_MODEL` (IDs `-latest` do OpenRouter levam `~`).
**Feito quando:** testes com transporte simulado; mock por env.
"""),
        I("api: regra de escalonamento por threshold", """
Se `verdict.uncertain` não é vazio → 1 chamada LLM; decisões incertas são substituídas e o veredito recalculado; `trace` registra a etapa. `t` default 0,7 (lab 05), configurável por env e por request (limitado a [0,5–0,95]).
**Feito quando:** testes cobrem: nada incerto (LLM não tocado), incerto (LLM acionado), LLM indisponível (mantém veredito do jev e sinaliza).
"""),
        I("web: slider de threshold recalculando no cliente", """
Slider muda `t` e recalcula lane e decisões incertas no browser, sem nova chamada, mostrando "com esse t o LLM seria acionado: sim/não". Porta `verdict()` pra TS com a mesma tabela de casos do Python (fixture compartilhada em JSON).
**Feito quando:** teste roda a fixture nos dois lados e os resultados batem.
"""),
        I("api: rate limit por IP", """
Janela deslizante em memória: N triagens/min e M/dia por IP (IP de `X-Forwarded-For` só quando vindo do Caddy). 429 com `Retry-After`.
**Feito quando:** teste cobre limite, reset e header forjado de fora.
"""),
        I("api: teto diário de chamadas LLM e de gasto", """
Contadores em memória com virada à meia-noite UTC: `MAX_LLM_CALLS_DAY`, `MAX_SPEND_DAY_USD`. Estourou → cascata desliga (resposta sinaliza "LLM indisponível hoje"), jev continua.
**Feito quando:** teste cobre estouro e virada do dia. Limitação aceita: reinício zera o contador.
"""),
        I("api: cache em memória por head sha", """
Chave `(owner, repo, number, head_sha, questions_version, t)`, LRU com teto de entradas e TTL. Resposta marca `cached: true`.
**Feito quando:** segundo pedido do mesmo PR não chama GitHub files, jev nem LLM.
"""),
        I("segurança: conteúdo do PR como dado não confiável", """
Título, descrição e diff são texto de terceiros. jev só devolve tipos (baixo risco). Prompt do LLM separa instrução de dado e pede JSON; justificativa renderizada como texto puro (React escapa; sem `dangerouslySetInnerHTML`). Limites de tamanho por campo. Teste com PR contendo "ignore as instruções…".
**Feito quando:** teste de injeção não altera o formato da saída e nada é renderizado como HTML.
"""),
    ]),
    E("[Épico] M4 — Empacotamento e deploy no oute-server", """
Marco 4: `jev-o-matic-test` no ar, no padrão do studio (LXC + docker compose + Caddy interno + Nginx/Certbot no host).
**Feito quando:** a URL pública responde e um PR de exemplo é triado de ponta a ponta.
""", [
        I("infra: docker-compose e Caddyfile", """
Serviços `api`, `web`, `caddy` (:80). Caddy: `/api/*` → api:8000, resto → web:8080, `trusted_proxies static private_ranges`, `auto_https off`. Sem banco, sem volume.
**Feito quando:** `docker compose up -d --build` sobe tudo e `curl localhost/api/health` responde (arm64).
"""),
        I("infra: .env.example e documentação de segredos", """
`OPENROUTER_API_KEY`, `GITHUB_TOKEN` (fine-grained, read-only público), `JEV_MODEL`, `LLM_MODEL`, limites. `docs/production.md` no formato do studio: forma, o que o servidor precisa, host, rollback.
**Feito quando:** alguém sobe o ambiente só com o doc.
"""),
        I("ops: provisionar LXC jev-o-matic-test", """
`lab/install-app.sh --name jev-o-matic-test --public`; registrar IP/porta em `lab/servers/oute-server/PORTS.md`; checkout em `/opt/app`; `.env` modo 600; segredos no Vaultwarden.
**Feito quando:** compose rodando dentro do container.
""", who=HUMAN),
        I("ops: DNS, vhost Nginx e certificado", """
Subdomínio (sugestão `jev.oute.pro`) → vhost no host → `<ip-do-container>:80`, Certbot, redirect HTTP→HTTPS, `X-Forwarded-Proto https`.
**Feito quando:** `https://<domínio>/api/health` responde de fora da Tailscale.
""", who=HUMAN),
        I("ci: checks de api e web", """
Workflow `ci.yml`: api (ruff, mypy, pytest), web (oxlint, tsc, bun test, build). Sem CD automático nesta fase — deploy manual por `git pull && docker compose up -d --build`.
**Feito quando:** CI verde na main e obrigatório em PR.
"""),
        I("ops: smoke pós-deploy", """
Script que bate em `/api/health` e tria 1 PR de exemplo contra a URL pública, validando o schema.
**Feito quando:** roda verde contra `jev-o-matic-test`.
"""),
    ]),
    E("[Épico] M5 — Lab 09: validação com PRs rotulados", """
Hoje a demo mostra, não prova: não existe ground truth de PR. Este épico mede acerto, no formato dos labs 00/03/08.
**Feito quando:** achados publicados no Project com acerto por pergunta, cobertura por threshold e erros reais vs rótulo discutível.
""", [
        I("lab 09: coletar ~50 PRs públicos variados", """
Amostra estratificada (docs, deps, feature, bugfix, segurança, migração, infra, refactor), de 8–10 repos conhecidos. Salvar o state congelado por head sha em `datasets/prs_v1.jsonl` (reprodutível sem GitHub).
**Feito quando:** dataset versionado com a distribuição documentada.
"""),
        I("lab 09: rotular os PRs", """
Rótulos pras 8 perguntas + lane esperada. Rascunho por Claude, **revisão do Bardi em 100%** (lição do lab 05: dataset rotulado só por LLM favorece o LLM avaliado).
**Feito quando:** rótulos revisados e critérios de rotulagem escritos.
""", who=HUMAN),
        I("lab 09: runner e análise", """
`labs/09_pr_triage`: roda jev (e LLM) no dataset; análise offline: acerto por pergunta, confidence vs acerto, cobertura por t, lane correta, custo/latência, cascata.
**Feito quando:** `uv run lab 09` e `--offline` funcionam.
"""),
        I("lab 09: ajustar wording e publicar achados", """
Iterar `questions.py` com split treino/teste (lição do lab 04), bump de `QUESTIONS_VERSION`, achados no Project, números reais no aviso da demo.
**Feito quando:** doc de achados publicado e demo atualizada.
"""),
    ]),
]


def gh(*args: str, stdin: str | None = None) -> str:
    r = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"gh {' '.join(args[:4])}… falhou:\n{r.stderr}")
    return r.stdout


def walk(nodes: list, depth: int = 0):
    for n in nodes:
        yield n, depth
        yield from walk(n["subs"], depth + 1)


def main() -> None:
    flat = list(walk(TREE))
    if "--dry-run" in sys.argv:
        for n, d in flat:
            print(f"{'  ' * d}- {n['title']}  [{', '.join(n['labels'])}]")
        print(f"\n{len(flat)} issues ({sum(d == 0 for _, d in flat)} épicos, "
              f"{sum(d == 1 for _, d in flat)} issues, {sum(d == 2 for _, d in flat)} sub-issues)")
        return

    for name, (color, desc) in LABELS.items():
        gh("label", "create", name, "--repo", REPO, "--color", color, "--description", desc, "--force")
    existing = {i["title"]: i for i in json.loads(
        gh("issue", "list", "--repo", REPO, "--state", "all", "--limit", "500", "--json", "title,number"))}

    def ensure(node: dict) -> tuple[int, int]:
        if node["title"] in existing:
            number = existing[node["title"]]["number"]
            print(f"= #{number} {node['title']}")
        else:
            payload = {"title": node["title"], "body": node["body"], "labels": node["labels"]}
            number = json.loads(gh("api", f"repos/{REPO}/issues", "--input", "-", stdin=json.dumps(payload)))["number"]
            print(f"+ #{number} {node['title']}")
        ident = json.loads(gh("api", f"repos/{REPO}/issues/{number}"))["id"]
        return number, ident

    def build(node: dict) -> int:
        number, ident = ensure(node)
        linked = {s["id"] for s in json.loads(gh("api", f"repos/{REPO}/issues/{number}/sub_issues", "--paginate"))} \
            if node["subs"] else set()
        for sub in node["subs"]:
            sub_id = build(sub)
            if sub_id not in linked:
                gh("api", f"repos/{REPO}/issues/{number}/sub_issues", "-X", "POST", "-F", f"sub_issue_id={sub_id}")
        return ident

    for epic in TREE:
        build(epic)
    print(f"\nok: https://github.com/{REPO}/issues")


if __name__ == "__main__":
    main()
