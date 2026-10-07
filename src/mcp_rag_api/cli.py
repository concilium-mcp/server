"""Linha de comando: servir (HTTP/stdio), migrar, sincronizar agentes, limpeza."""

import argparse
import asyncio
from pathlib import Path

from . import db


async def _sync_agents(out_dir: Path) -> list[Path]:
    """Gera .claude/agents/<slug>.md a partir do banco (fonte da verdade continua sendo o banco)."""
    await db.init_pool()
    try:
        rows = await db.pool().fetch(
            "SELECT slug, name, description, system_prompt FROM agents WHERE status = 'active' ORDER BY slug"
        )
    finally:
        await db.close_pool()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for r in rows:
        description = (r["description"] or r["name"]).replace("\n", " ")
        path = out_dir / f"{r['slug']}.md"
        path.write_text(
            f"---\nname: {r['slug']}\ndescription: {description}\n---\n\n"
            f"<!-- Gerado por `mcp-rag-api sync-agents`. Edite pelo MCP (update_agent), não aqui. -->\n\n"
            f'No início, chame a tool load_agent com agent_slug="{r["slug"]}" para carregar memórias, '
            f"último resumo e tarefas. Ao terminar, chame save_session.\n\n{r['system_prompt']}\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


async def _cleanup() -> dict:
    from .core.memory import cleanup_memories

    await db.init_pool()
    try:
        return await cleanup_memories()
    finally:
        await db.close_pool()


def main() -> None:
    parser = argparse.ArgumentParser(prog="mcp-rag-api")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="API REST + MCP (streamable HTTP em /mcp)")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    sub.add_parser("stdio", help="MCP via stdio (usa KB_API_KEY)")
    sub.add_parser("migrate", help="Aplica migrações pendentes")

    sync = sub.add_parser("sync-agents", help="Gera .claude/agents/<slug>.md a partir do banco")
    sync.add_argument("--out", type=Path, default=Path(".claude/agents"))

    sub.add_parser("cleanup", help="Remove memórias expiradas")

    args = parser.parse_args()
    match args.cmd:
        case "serve":
            import uvicorn

            from .logging_config import setup_logging

            setup_logging()
            uvicorn.run("mcp_rag_api.main:app", host=args.host, port=args.port, reload=args.reload)
        case "stdio":
            from .mcp_server import mcp

            mcp.run("stdio")
        case "migrate":
            applied = asyncio.run(db.run_migrations())
            print("Aplicadas:", ", ".join(applied) if applied else "nenhuma (já atualizado)")
        case "sync-agents":
            for path in asyncio.run(_sync_agents(args.out)):
                print("escrito:", path)
        case "cleanup":
            print(asyncio.run(_cleanup()))


if __name__ == "__main__":
    main()
