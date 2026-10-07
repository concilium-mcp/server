"""Testes de integração da superfície HTTP (TestClient): semântica 401/403, docs, body limit e chave read-only.

Precisam do banco de teste (TEST_DATABASE_URL): o lifespan do app roda migrações e o pool.
O TestClient roda o lifespan no loop do portal dele, então cada teste fecha o pool da
sessão antes e o recria ao final.
"""

import pytest
from fastapi.testclient import TestClient

from mcp_rag_api import db
from mcp_rag_api.config import get_settings

ADMIN = "chave-admin-teste"
READ_ONLY = "chave-somente-leitura"


@pytest.fixture
def http_env(monkeypatch, request):
    monkeypatch.setenv("KB_API_KEY", ADMIN)
    monkeypatch.setenv("KB_READ_ONLY_KEY", READ_ONLY)
    monkeypatch.setenv("KB_AUTH_DISABLED", "false")
    for key, value in getattr(request, "param", {}).items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client(http_env):
    await db.close_pool()
    from mcp_rag_api.main import create_app

    with TestClient(create_app()) as c:
        yield c
    await db.init_pool()


# ---------------------------------------------------------------- autenticação


def test_sem_chave_retorna_401_com_www_authenticate(client):
    r = client.get("/collections")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert "detail" in r.json()


def test_chave_invalida_retorna_401(client):
    r = client.get("/collections", headers={"Authorization": "Bearer errada"})
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_chave_admin_autentica(client):
    r = client.get("/collections", headers={"Authorization": f"Bearer {ADMIN}"})
    assert r.status_code == 200


# ---------------------------------------------------------------- docs


def test_docs_desligado_por_padrao(client):
    # sem chave, cai no portão do /mcp (401); com chave, a rota simplesmente não existe (404)
    assert client.get("/docs").status_code == 401
    assert client.get("/openapi.json").status_code == 401
    headers = {"Authorization": f"Bearer {ADMIN}"}
    assert client.get("/docs", headers=headers).status_code == 404
    assert client.get("/openapi.json", headers=headers).status_code == 404


@pytest.mark.parametrize("http_env", [{"KB_DOCS_ENABLED": "true"}], indirect=True)
def test_docs_reativado_com_env(client):
    assert client.get("/docs").status_code == 200
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "MCP RAG API"


# ---------------------------------------------------------------- body limit


@pytest.mark.parametrize("http_env", [{"KB_MAX_BODY_BYTES": "64"}], indirect=True)
def test_payload_grande_retorna_413(client):
    r = client.post(
        "/search",
        content=b'{"query": "' + b"x" * 128 + b'"}',
        headers={"Authorization": f"Bearer {ADMIN}", "Content-Type": "application/json"},
    )
    assert r.status_code == 413
    assert "limite" in r.json()["detail"]


@pytest.mark.parametrize("http_env", [{"KB_MAX_BODY_BYTES": "1024"}], indirect=True)
def test_payload_abaixo_do_limite_passa_do_middleware(client):
    # chave admin + payload dentro do limite: não é 413 (o request passa pelo middleware)
    r = client.post(
        "/search",
        content=b'{"query": "' + b"x" * 512 + b'"}',
        headers={"Authorization": f"Bearer {ADMIN}", "Content-Type": "application/json"},
    )
    assert r.status_code != 413


# ---------------------------------------------------------------- chave read-only


def test_read_only_le_mas_nao_escreve(client):
    headers = {"Authorization": f"Bearer {READ_ONLY}"}
    r = client.get("/collections", headers=headers)
    assert r.status_code == 200

    r = client.post("/collections", json={"name": "bloqueada"}, headers=headers)
    assert r.status_code == 403  # escopo insuficiente: não é 401, sem WWW-Authenticate
    assert "WWW-Authenticate" not in r.headers

    r = client.post(
        "/documents",
        json={"collection": "manuais", "title": "X", "content": "conteúdo"},
        headers=headers,
    )
    assert r.status_code == 403

    r = client.post("/search", json={"query": "reembolso"}, headers=headers)
    assert r.status_code == 200


def test_admin_escrita_ok(client):
    r = client.post(
        "/collections",
        json={"name": "manuais"},
        headers={"Authorization": f"Bearer {ADMIN}"},
    )
    assert r.status_code == 200
