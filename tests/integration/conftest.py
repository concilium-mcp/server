"""Testes de integração contra Postgres + pgvector reais.

Rode com: TEST_DATABASE_URL=postgresql://user:password@localhost:5432/kb_test_s02 pytest tests/integration
O banco indicado é APAGADO (schema public recriado) a cada execução.
Por segurança, o nome do banco deve conter "test" — a execução aborta caso contrário.
"""

import os
from urllib.parse import urlparse

import asyncpg
import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")


def _check_test_database_url(url: str) -> None:
    """Trava de segurança: só permite bancos com "test" no nome (ex.: kb_test_s02)."""
    db_name = urlparse(url).path.lstrip("/")
    if "test" not in db_name.lower():
        raise RuntimeError(
            f"TEST_DATABASE_URL aponta para '{db_name}', que não parece um banco de testes "
            '(o nome deve conter "test"). Recusando destruir o schema public desse banco.'
        )


def pytest_collection_modifyitems(config, items):
    if TEST_DB:
        return
    skip = pytest.mark.skip(reason="defina TEST_DATABASE_URL para rodar os testes de integração")
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
async def database():
    if not TEST_DB:
        yield
        return
    _check_test_database_url(TEST_DB)
    os.environ["DATABASE_URL"] = TEST_DB
    os.environ["EMBEDDING_PROVIDER"] = "fake"
    os.environ["KB_AUTH_DISABLED"] = "false"
    from mcp_rag_api import db
    from mcp_rag_api.config import get_settings
    from mcp_rag_api.core.embeddings import get_embedder

    get_settings.cache_clear()
    get_embedder.cache_clear()

    conn = await asyncpg.connect(TEST_DB)
    await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    await conn.close()

    await db.run_migrations()
    await db.init_pool()
    yield
    await db.close_pool()
