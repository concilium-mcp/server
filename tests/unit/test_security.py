import pytest

from mcp_rag_api.config import Settings
from mcp_rag_api.security import (
    KBError,
    PermissionDenied,
    Principal,
    bearer_token,
    resolve_env_key,
    validate_scopes,
)


@pytest.fixture
def env_key(monkeypatch):
    monkeypatch.setattr(
        "mcp_rag_api.security.get_settings", lambda: Settings(kb_api_key="segredo-de-teste")
    )


def test_resolve_env_key_ok(env_key):
    p = resolve_env_key("segredo-de-teste")
    assert p.actor == "env:kb_api_key"
    assert p.has("admin") and p.is_manager


def test_resolve_env_key_rejects_wrong_token(env_key):
    with pytest.raises(PermissionDenied):
        resolve_env_key("outra-chave")


def test_resolve_env_key_without_configured_key(monkeypatch):
    monkeypatch.setattr("mcp_rag_api.security.get_settings", lambda: Settings(kb_api_key=""))
    with pytest.raises(PermissionDenied):
        resolve_env_key("qualquer-uma")


def test_scope_implications():
    writer = Principal(actor="a", scopes=frozenset({"write"}))
    assert writer.has("read") and writer.has("write")
    assert not writer.has("agents:manage")
    admin = Principal(actor="b", scopes=frozenset({"admin"}))
    assert admin.has("agents:manage") and admin.is_manager
    with pytest.raises(PermissionDenied):
        writer.require("agents:manage")


def test_collection_restriction():
    p = Principal(actor="a", scopes=frozenset({"read"}), allowed_collections=("manuais",))
    assert p.collection_filter(None) == ["manuais"]
    assert p.collection_filter(["manuais"]) == ["manuais"]
    with pytest.raises(PermissionDenied):
        p.collection_filter(["financeiro"])
    unrestricted = Principal(actor="b", scopes=frozenset({"read"}))
    assert unrestricted.collection_filter(None) is None


def test_validate_scopes():
    assert validate_scopes(["write", "read", "read"]) == ["read", "write"]
    with pytest.raises(KBError):
        validate_scopes(["root"])


def test_bearer_token():
    assert bearer_token("Bearer abc") == "abc"
    assert bearer_token("bearer  abc ") == "abc"
    assert bearer_token("Basic abc") is None
    assert bearer_token(None) is None
