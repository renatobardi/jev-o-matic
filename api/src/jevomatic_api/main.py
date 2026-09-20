"""App FastAPI. Tudo fica sob /api — o Caddy roteia /api/* pra cá e o resto pro web."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__
from .errors import TriageError
from .schemas import ErrorOut, TriageRequest, TriageResponse
from .triage import triage

app = FastAPI(
    title="jev-o-matic PR Triage",
    version=__version__,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
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
    return _error("invalid_request", 'Corpo inválido: envie {"url": "…", "t"?: 0.5–0.95}.', 422)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post(
    "/api/triage",
    responses={
        422: {"model": ErrorOut},
        404: {"model": ErrorOut},
        429: {"model": ErrorOut},
        502: {"model": ErrorOut},
    },
)
async def post_triage(body: TriageRequest) -> TriageResponse:
    return await triage(body.url, body.t)
