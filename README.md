# jev-o-matic

Lab para estudar o **jev**, modelo System One da TypeSafe: decisões tipadas (`noul` / `choice` / `score`) com probabilidade, em vez de texto.

Cada lab é um script pequeno que responde uma pergunta com dados reais e grava o resultado bruto em `results/`.

## Setup

```bash
uv sync
cp .env.example .env   # preencher OPENROUTER_API_KEY
uv run lab 01
```

Backend atual: OpenRouter Decisions API (alpha), modelo `typesafe/jev-1.13`. O `harness/client.py` isola o backend — trocar pelo `typesafe-sdk` oficial não muda os labs.

## Labs

| # | Pergunta | Status |
|---|---|---|
| 00 dataset-run | Roda `datasets/tickets_v1.jsonl` (101 tickets, PT+EN); base dos labs 03/07/08 | pronto |
| 01 primitives | Como é a resposta de cada primitivo? | pronto |
| 02 fanout | 1 vs 20 perguntas na mesma chamada: latência, custo, drift? | pronto |
| 03 confidence-routing | Qual threshold separa código / LLM / humano? | pronto (offline) |
| 04 composite-scoring | Julgamento único vs dimensões + pesos | — |
| 05 cascade | jev→LLM: economia vs tudo no LLM | — |
| 06 jaggedness | Onde erra (retratação, terceiro, negação, contagem, datas) e o wording mitiga? | pronto |
| 07 pt-br | PT-BR degrada vs EN? | pronto (offline) |
| 08 calibration | Confidence bate com acerto real? | pronto (offline) |

## Estrutura

```
harness/   cliente, normalização de resposta, log de runs, CLI
labs/      um diretório por experimento (run.py)
datasets/  dados rotulados
results/   JSONL por execução (versionado: é o dado bruto do lab)
```
