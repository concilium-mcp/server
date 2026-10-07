"""Logging do servidor: logger 'mcp_rag_api' com nível via KB_LOG_LEVEL (default INFO).

Regras: nunca logar segredos (chaves de API) nem conteúdo de documentos.
"""

import logging
from contextvars import ContextVar

from .config import get_settings

LOGGER_NAME = "mcp_rag_api"

# Id da requisição HTTP atual; preenchido pelo RequestIdMiddleware.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class _RequestIdFilter(logging.Filter):
    """Injeta o request-id em todo registro emitido dentro do contexto da requisição."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def setup_logging() -> None:
    """Configura o logger do pacote (idempotente). Chamado no lifespan e no 'cli serve'."""
    level = getattr(logging, get_settings().kb_log_level.upper(), logging.INFO)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
        handler.addFilter(_RequestIdFilter())
        logger.addHandler(handler)
