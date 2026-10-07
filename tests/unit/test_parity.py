"""Paridade MCP × REST: toda tool MCP precisa de rota REST equivalente (ou exceção justificada).

Se uma tool nascer sem rota, este teste falha — ou a rota é adicionada em api.py, ou a tool
entra em REST_EXCEPTIONS com justificativa.
"""

from mcp_rag_api.api import router
from mcp_rag_api.mcp_server import mcp

# tool MCP → (método, path) da rota REST que a espelha.
# add_agent_memory/add_agent_task compartilham rota com remember/upsert_task: executam a
# mesma função de core (a variante "manage" só reforça o escopo agents:manage no MCP).
MCP_TO_REST: dict[str, tuple[str, str]] = {
    # base de conhecimento
    "search_knowledge": ("POST", "/search"),
    "get_document": ("GET", "/documents/{document_id}"),
    "list_documents": ("GET", "/documents"),
    "list_collections": ("GET", "/collections"),
    "create_collection": ("POST", "/collections"),
    "add_document": ("POST", "/documents"),
    "update_document": ("PATCH", "/documents/{document_id}"),
    "upsert_document": ("PUT", "/documents/upsert"),
    "archive_document": ("DELETE", "/documents/{document_id}"),
    "document_history": ("GET", "/documents/{document_id}/versions"),
    # agente: contexto, memória, sessões e tarefas
    "load_agent": ("GET", "/agents/{slug}/context"),
    "recall": ("GET", "/agents/{slug}/memories"),
    "remember": ("POST", "/agents/{slug}/memories"),
    "forget": ("POST", "/agents/{slug}/memories:forget"),
    "save_session": ("POST", "/agents/{slug}/sessions"),
    "list_sessions": ("GET", "/agents/{slug}/sessions"),
    "list_tasks": ("GET", "/agents/{slug}/tasks"),
    "upsert_task": ("POST", "/agents/{slug}/tasks"),
    # gestão de agentes (agents:manage)
    "create_agent": ("POST", "/agents"),
    "update_agent": ("PATCH", "/agents/{slug}"),
    "set_agent_autonomy": ("PUT", "/agents/{slug}/autonomy"),
    "get_agent": ("GET", "/agents/{slug}"),
    "list_agents": ("GET", "/agents"),
    "clone_agent": ("POST", "/agents/{slug}/clone"),
    "archive_agent": ("DELETE", "/agents/{slug}"),
    "restore_agent_version": ("POST", "/agents/{slug}/versions/{version}/restore"),
    "list_agent_proposals": ("GET", "/agents/proposals"),
    "review_agent_update": ("POST", "/agents/proposals/{proposal_id}/review"),
    "add_agent_memory": ("POST", "/agents/{slug}/memories"),
    "add_agent_task": ("POST", "/agents/{slug}/tasks"),
}

# Tools sem equivalente REST, com justificativa:
# - propose_agent_update: é o fluxo do agente conversando sobre o próprio perfil; por REST,
#   quem gerencia aplica a mudança direto com PATCH /agents/{slug} (gera versão igual).
REST_EXCEPTIONS = {"propose_agent_update"}


def _rest_routes() -> set[tuple[str, str]]:
    return {(method, route.path) for route in router.routes for method in route.methods}


async def test_every_mcp_tool_has_rest_route() -> None:
    tools = {t.name for t in await mcp.list_tools()}
    assert tools == set(MCP_TO_REST) | REST_EXCEPTIONS, (
        f"tools sem rota REST mapeada (ou mapeamento órfão): {tools ^ (set(MCP_TO_REST) | REST_EXCEPTIONS)}"
    )
    rest = _rest_routes()
    missing = {name: spec for name, spec in MCP_TO_REST.items() if spec not in rest}
    assert not missing, f"tools cuja rota REST não existe: {missing}"
