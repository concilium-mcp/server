"""Observabilidade HTTP: request-id no header e nos logs, handler de 500 e resumo de boot."""

import logging

from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from mcp_rag_api import db
from mcp_rag_api.config import Settings
from mcp_rag_api.main import _log_boot_summary, app


class _FakePool:
    async def fetchval(self, _query: str) -> int:
        return 1


async def test_request_id_no_header(monkeypatch):
    monkeypatch.setattr(db, "pool", lambda: _FakePool())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id")


def test_500_devolve_json_generico_e_loga(monkeypatch, caplog):
    """Handler de Exception vira o handler do ServerErrorMiddleware: responde 500 e loga.

    raise_server_exceptions=False porque o middleware re-lança a exceção após responder
    (comportamento normal em produção, onde o servidor registra o traceback no log).
    """
    def _boom():
        raise RuntimeError("falha inesperada")

    monkeypatch.setattr(db, "pool", _boom)
    monkeypatch.setattr(logging.getLogger("mcp_rag_api"), "propagate", True)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 500
    assert "falha inesperada" not in str(resp.json())
    assert resp.headers.get("X-Request-Id")
    assert any("erro 500" in r.getMessage() for r in caplog.records)


def test_boot_summary_loga_config_sem_segredos(monkeypatch, caplog):
    fake_settings = Settings(kb_api_key="segredo-super-secreto", embedding_provider="fake")
    monkeypatch.setattr("mcp_rag_api.main.get_settings", lambda: fake_settings)
    monkeypatch.setattr(logging.getLogger("mcp_rag_api"), "propagate", True)
    with caplog.at_level(logging.INFO, logger="mcp_rag_api"):
        _log_boot_summary()
    mensagens = [r.getMessage() for r in caplog.records]
    assert any("embedding_provider=fake" in m for m in mensagens)
    assert not any("segredo-super-secreto" in m for m in mensagens)


def test_boot_warning_gritante_quando_auth_desabilitado(monkeypatch, caplog):
    fake_settings = Settings(kb_auth_disabled=True)
    monkeypatch.setattr("mcp_rag_api.main.get_settings", lambda: fake_settings)
    monkeypatch.setattr(logging.getLogger("mcp_rag_api"), "propagate", True)
    with caplog.at_level(logging.WARNING, logger="mcp_rag_api"):
        _log_boot_summary()
    assert any("KB_AUTH_DISABLED" in r.getMessage() for r in caplog.records)
