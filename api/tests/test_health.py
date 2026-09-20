from fastapi.testclient import TestClient

from jevomatic_api import __version__
from jevomatic_api.main import app


def test_health() -> None:
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": __version__}
