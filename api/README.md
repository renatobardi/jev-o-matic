# jevomatic-api

Serviço FastAPI do jev-o-matic v2 (PR Triage).

```bash
uv sync
uv run --env-file ../.env uvicorn jevomatic_api.main:app --reload --port 8000   # .env da raiz: OPENROUTER_API_KEY, GITHUB_TOKEN
uv run pytest -q && uv run ruff check && uv run mypy src
```
