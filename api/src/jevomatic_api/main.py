"""App FastAPI. Tudo fica sob /api — o Caddy roteia /api/* pra cá e o resto pro web."""

from fastapi import FastAPI

from . import __version__

app = FastAPI(
    title="jev-o-matic PR Triage",
    version=__version__,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
