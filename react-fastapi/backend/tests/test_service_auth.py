"""
service_auth.py の回帰テスト(interview_app / react-fastapi向け)。

conftest.py はLAUNCH_FASTAPI_ORCHESTRATED=1をデフォルトにして、既存の
テスト群がgatewayのCookie無しで動くようにしている。ここではその
デフォルトを明示的に外し、gateway統合時の本来の挙動(未認証は401)を
確認する。main.py全体(DB初期化・core_sync bootstrap等)を起動すると
重くなるため、service_auth_middlewareだけを最小のFastAPIアプリに
載せてテストする。
"""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import service_auth


@pytest.fixture()
def client(monkeypatch):
    # conftest.pyのデフォルト(LAUNCH_FASTAPI_ORCHESTRATED=1)を、この
    # テストファイルの中でだけ明示的に外す。
    monkeypatch.delenv("LAUNCH_FASTAPI_ORCHESTRATED", raising=False)
    monkeypatch.setenv("GATEWAY_AUTH_TOKEN", "test-token-12345")

    app = FastAPI()
    app.middleware("http")(service_auth.service_auth_middleware)

    @app.get("/docs")
    def docs():
        return {"ok": True}

    @app.get("/api/v1/health")
    def health():
        return {"ok": True}

    @app.get("/api/v1/sessions")
    def list_sessions():
        return {"sessions": []}

    @app.get("/")
    def spa_shell():
        return {"ok": True}

    return TestClient(app)


def test_public_paths_allowed_without_cookie(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/").status_code == 200  # SPAシェル(gatewayの"/"と同じ扱い)


def test_api_path_rejected_without_cookie(client):
    resp = client.get("/api/v1/sessions")
    assert resp.status_code == 401


def test_api_path_allowed_with_correct_token(client):
    client.cookies.set(service_auth.SESSION_COOKIE_NAME, "test-token-12345")
    resp = client.get("/api/v1/sessions")
    assert resp.status_code == 200


def test_api_path_rejected_with_wrong_token(client):
    client.cookies.set(service_auth.SESSION_COOKIE_NAME, "wrong-token")
    resp = client.get("/api/v1/sessions")
    assert resp.status_code == 401


def test_standalone_mode_bypasses_auth_entirely(client, monkeypatch):
    # launch_fastapi.py経由(単体exe)の起動を模す。Cookie無しでも通ることを確認する。
    monkeypatch.setenv("LAUNCH_FASTAPI_ORCHESTRATED", "1")
    resp = client.get("/api/v1/sessions")
    assert resp.status_code == 200
