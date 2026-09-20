# Rubrica de rotulagem — `prs_v1` (lab 09, #40)

Dois rotuladores às cegas (Bardi e Claude), mesma rubrica, sem ver o rótulo um do outro nem a
resposta do jev. Depois: concordância por pergunta → discussão só das discordâncias → rótulo final.
A taxa de discordância é achado do lab: onde dois humanos não concordam, não dá pra cobrar o jev.

## Regras gerais

1. **Rotule lendo o diff completo no GitHub** (aba *Files changed*), não o título. O `hint` do
   dataset é só o estrato da busca — não é rótulo (lição do werkzeug#3252).
2. **Rotule a realidade, não o que o jev conseguiria ver.** Use o que você sabe como engenheiro
   (ex.: que tal classe é API pública do framework). Se a resposta certa só dá
   pra saber com contexto de FORA do diff, rotule a certa e marque `fora_do_diff = sim`. Isso
   separa depois "o jev errou" de "era impossível acertar só com o diff".
3. **Na dúvida real, escolha a melhor resposta e marque `duvida = sim`** (com uma nota curta).
   Não deixe em branco. PR com dúvida entra na análise separado.
4. **Não abra** `prs_v1_claude.*`, `results/` do lab 09 nem rode o PR na demo antes de terminar.
5. Sem pressa de acertar "o que o sistema daria": a coluna `via` é a SUA decisão de revisor.

## Perguntas

### `change_type` — o que o PR é, pelo que o diff faz
| valor | quando |
|---|---|
| `feature` | comportamento novo observável por usuário/chamador. Teste e doc de apoio junto NÃO mudam o tipo |
| `bugfix` | corrige comportamento errado de código que já existia. Teste e doc de apoio junto NÃO mudam o tipo |
| `refactor` | reestrutura sem mudar comportamento. **Remover API depreciada** = `refactor` se for só limpeza prometida; o quebra-contrato vai em `breaking_api` |
| `deps` | só versão de dependência / lockfile / vendored |
| `docs` | só documentação, comentário, docstring, tradução, exemplo — **mesmo que o arquivo seja `.rb`/`.rs`/`.py`** (doc comment em código é docs) |
| `config_infra` | só CI, build, deploy, tooling, configuração |
| `tests_only` | só testes |
| `mixed` | duas ou mais mudanças INDEPENDENTES e nenhuma domina (bugfix + refactor não relacionado + bump) |

### `risk` — o código mais sensível que o diff toca (0 / 1 / 2)
- **0** — nada que roda em produção: docs, comentários, testes, formatação, tradução, bump de
  versão, CI/linters/tooling de dev.
- **1** — código comum de produção: lógica de negócio, UI, rendering, parsing, formatação de
  saída, helpers, logging, mensagens de erro, CLI.
- **2** — código crítico: autenticação/autorização/segredos (inclui sanitização de entrada com
  efeito de segurança); migração ou estrutura de dado persistido; remoção/mudança de assinatura de
  interface pública; manifest de deploy / IaC que a produção roda; cálculo ou movimentação de
  dinheiro; locks/transações/retries/idempotência/invalidação de cache; código que apaga, trunca
  ou sobrescreve dado persistido.
- Bump de dependência que corrige CVE: **0** (o diff não toca código nosso). A urgência do CVE não é risco do diff.
- Dockerfile/compose/workflow que **publica ou faz deploy** = 2; workflow que só roda teste/lint = 0.

### Flags (sim / não)
- **`touches_auth_security`** — o diff adiciona/remove/modifica LÓGICA de autenticação, autorização,
  checagem de permissão, criptografia/TLS, segredos, sessão, CSRF/CORS ou sanitização de entrada.
  Palavra de segurança só em nome de arquivo, comentário, doc ou teste = **não**.
- **`touches_data_schema`** — muda a ESTRUTURA de dado persistido: migração, tabela/coluna/índice/FK,
  campo de model ORM, formato de arquivo/mensagem gravado. Mudar só query, tipo em memória ou
  payload de API = **não**. Migração de DADOS (backfill) sem mudar estrutura = **sim** (mexe no que
  está persistido via mecanismo de migração) — marque `duvida` se achar forçado.
- **`breaking_api`** — quem já usa uma interface PÚBLICA quebra: endpoint, função/classe exportada,
  flag de CLI, chave de config ou formato de mensagem removido, renomeado ou com entrada
  obrigatória/saída alterada. Adição compatível, aviso de depreciação e correção de bug que muda
  saída errada = **não**. Se só dá pra saber que é público por fora do diff → resposta real +
  `fora_do_diff = sim`.
- **`touches_infra_ci`** — muda como o projeto é buildado, testado no CI ou implantado: workflow,
  Dockerfile, compose, manifest, IaC, pipeline. Só versão de dependência de app = **não**.
- **`has_tests`** — o PR traz/altera teste automatizado que exercita o comportamento alterado.
  PR só de docs/deps/CI: **não** (não há o que testar — é informativo, não pesa na via).
- **`description_explains_why`** — a descrição do PR diz a motivação, o problema ou linka o issue,
  além de repetir o título. Vazia, template não preenchido ou só "o que mudou" = **não**.

### `via` — que revisão VOCÊ pediria, como dono do repo
- `fast` — aprova com uma olhada; erro aqui não machuca produção.
- `normal` — revisão comum de um par.
- `senior` — precisa de alguém experiente / dono da área; erro aqui custa caro ou é difícil de reverter.

Não derive a via das outras colunas nem da regra do `verdict.py`. É o seu julgamento — a análise
vai comparar (a) jev × rótulos, (b) regra aplicada aos rótulos × sua via. A segunda mede a REGRA.

## Casos de fronteira já conhecidos (decida e marque `duvida` se pesar)
- Doc comment em arquivo de código (`.rb`, `.rs`, `.py`…): `docs`, risk 0. O sistema hoje NÃO dá fast
  nesses (guarda por arquivo) — é trade-off conhecido, o lab mede quanto custa.
- Bump de dependência dentro de Dockerfile/compose: `deps` ou `config_infra`? → `deps` se é só a
  tag/versão; risk pela regra de deploy acima.
- Remover plugin/adaptador depreciado inteiro:
  `refactor` + `breaking_api = sim` + risk 2.
- Fix de bug em código de segurança que NÃO muda a regra de segurança (ex.: exceção num caminho de validação de token): `touches_auth_security = sim` (modifica a lógica), risk 2.

## Rubrica × wording do jev
A rubrica descreve o CONCEITO que queremos medir; não copia o wording `pr-v2`. Onde divergem de
propósito: sanitização de entrada conta como crítico no `risk` 2 (no `pr-v2` só está no flag de
segurança — desalinhamento anotado no doc 14). Divergência vira erro do jev na análise, que é o certo.
