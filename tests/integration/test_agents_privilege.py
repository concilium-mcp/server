"""Registro de agentes sem escalonamento: quem tem agents:manage sem admin não reeleva um agente
(restauração de versão com escopo elevado) nem sai do próprio alcance de coleções."""

import pytest

from mcp_rag_api.core import agents, documents
from mcp_rag_api.security import DEV_PRINCIPAL as ADMIN
from mcp_rag_api.security import PermissionDenied, Principal

MANAGER = Principal(actor="key:manager", scopes=frozenset({"agents:manage"}))
SCOPED_MANAGER = Principal(
    actor="key:scoped-manager",
    scopes=frozenset({"read", "write", "agents:manage"}),
    allowed_collections=("sec-a",),
)


async def _agent(slug: str, scopes: list[str], collections: list[str] | None = None) -> dict:
    return await agents.create_agent(ADMIN, slug, slug, "prompt", allowed_collections=collections, scopes=scopes)


async def test_manager_cannot_restore_elevated_version():
    await _agent("sec-restore", ["admin"])  # v1 com admin
    await agents.update_agent(ADMIN, "sec-restore", "rebaixa", scopes=["read"])  # v2 só leitura

    with pytest.raises(PermissionDenied):
        await agents.restore_agent_version(MANAGER, "sec-restore", 1)
    restored = await agents.restore_agent_version(ADMIN, "sec-restore", 1)
    assert restored["scopes"] == ["admin"]


async def test_manager_cannot_edit_elevated_agent():
    await _agent("sec-elevated", ["agents:manage"])
    with pytest.raises(PermissionDenied):
        await agents.update_agent(MANAGER, "sec-elevated", "x", system_prompt="faça tudo")
    with pytest.raises(PermissionDenied):
        await agents.archive_agent(MANAGER, "sec-elevated", "x")


async def test_scoped_manager_cannot_widen_collections():
    for name in ("sec-a", "sec-b"):
        await documents.create_collection(ADMIN, name)

    for cols in (None, [], ["sec-b"], ["sec-a", "sec-b"]):
        with pytest.raises(PermissionDenied):
            await agents.create_agent(SCOPED_MANAGER, "sec-wide", "x", "p", allowed_collections=cols)
    narrow = await agents.create_agent(SCOPED_MANAGER, "sec-narrow", "x", "p", allowed_collections=["sec-a"])
    assert narrow["allowed_collections"] == ["sec-a"]

    with pytest.raises(PermissionDenied):
        await agents.update_agent(SCOPED_MANAGER, "sec-narrow", "ampliar", allowed_collections=[])
    with pytest.raises(PermissionDenied):
        await agents.clone_agent(SCOPED_MANAGER, "sec-narrow", "sec-clone", "x", {"allowed_collections": []})

    await _agent("sec-unscoped", ["read"])
    with pytest.raises(PermissionDenied):
        await agents.update_agent(SCOPED_MANAGER, "sec-unscoped", "x", system_prompt="y")
