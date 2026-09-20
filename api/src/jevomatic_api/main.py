"""App FastAPI. Tudo fica sob /api — o Caddy roteia /api/* pra cá e o resto pro web."""

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__
from .errors import TriageError
from .guards import TtlCache, budget_from_env, rate_limiter_from_env
from .schemas import ErrorOut, TriageRequest, TriageResponse
from .triage import Guards, triage

app = FastAPI(
    title="jev-o-matic PR Triage",
    version=__version__,
    # Swagger e o schema só com API_DOCS=1 (dev). Em produção não há por que publicar o mapa da API.
    docs_url="/api/docs" if os.getenv("API_DOCS") == "1" else None,
    openapi_url="/api/openapi.json" if os.getenv("API_DOCS") == "1" else None,
    redoc_url=None,
)


def _error(code: str, message: str, status: int, retry_after: int | None = None) -> JSONResponse:
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    return JSONResponse(
        {"error": {"code": code, "message": message}}, status_code=status, headers=headers
    )


@app.exception_handler(TriageError)
async def _triage_error(_: Request, e: TriageError) -> JSONResponse:
    return _error(e.code, e.message, e.status, e.retry_after)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, e: RequestValidationError) -> JSONResponse:
    return _error("invalid_request", 'Invalid body: send {"url": "…", "t"?: 0.5–0.95}.', 422)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


# Um conjunto de guardas por processo (a api roda com 1 worker — ver Dockerfile).
GUARDS = Guards(rate=rate_limiter_from_env(), budget=budget_from_env(), cache=TtlCache())


def client_ip(request: Request) -> str:
    """IP já resolvido pelo uvicorn a partir do X-Forwarded-For que o Caddy repassa.
    A garantia contra header forjado é de borda: o Caddy só confia em proxy de faixa privada e o
    Nginx do host deve SOBRESCREVER o X-Forwarded-For com $remote_addr (docs/production.md)."""
    return request.client.host if request.client else "unknown"


@app.post(
    "/api/triage",
    responses={code: {"model": ErrorOut} for code in (404, 422, 429, 502, 503)},
)
async def post_triage(body: TriageRequest, request: Request) -> TriageResponse:
    return await triage(body.url, body.t, guards=GUARDS, client_ip=client_ip(request))
