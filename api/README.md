# jevomatic-api

Serviço FastAPI do jev-o-matic v2 (PR Triage).

```bash
uv sync
uv run uvicorn jevomatic_api.main:app --reload --port 8000
uv run pytest -q && uv run ruff check && uv run mypy src
```
