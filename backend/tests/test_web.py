from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.web import mount_frontend


def test_hosted_client_routes_preserve_api_and_missing_assets(tmp_path):
    (tmp_path / "index.html").write_text("<h1>LIMBER</h1>")
    app = FastAPI()
    mount_frontend(app, tmp_path)
    client = TestClient(app)
    assert client.get("/camera").status_code == 200
    assert "LIMBER" in client.get("/progress").text
    assert client.get("/api/not-real").status_code == 404
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/.env").status_code == 404


def test_hosted_postgres_url_uses_installed_driver():
    assert Settings(database_url="postgresql://u:p@db/name").database_url == "postgresql+psycopg://u:p@db/name"
