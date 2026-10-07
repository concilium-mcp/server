"""App HTTP: API REST (FastAPI) + endpoint MCP streamable HTTP em /mcp."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import db
from .api import router
from .config import EMBEDDING_DIM, get_settings
from .core.embeddings import close_embedder, get_embedder
from .logging_config import get_logger, request_id_ctx, setup_logging
from .mcp_server import mcp
from .security import KBError, NotFound, PermissionDenied, bearer_token, resolve_env_key

logger = get_logger()

# Precisa ser criado antes do lifespan: é aqui que o MCPServer instancia o session manager.
# host="0.0.0.0" evita a proteção automática que só aceita Host localhost (atrás de proxy/domínio).
mcp_app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, host="0.0.0.0")


def _log_boot_summary() -> None:
    """Resumo de config no boot: provider, dim e modo de auth — nunca segredos."""
    s = get_settings()
    auth_mode = "DESABILITADA" if s.kb_auth_disabled else "chave única (KB_API_KEY)"
    logger.info("boot: embedding_provider=%s embedding_dim=%d auth=%s", s.embedding_provider, EMBEDDING_DIM, auth_mode)
    if s.kb_auth_disabled:
        logger.warning("KB_AUTH_DISABLED=true: AUTENTICAÇÃO DESLIGADA — use apenas em desenvolvimento!")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    _log_boot_summary()
    if get_settings().embedding_provider == "local":
        # Pré-carrega o modelo (~2 GB) fora do caminho das requisições.
        await get_embedder().warmup()
    try:
        async with db.lifespan(), mcp.session_manager.run():
            yield
    finally:
        await close_embedder()


app = FastAPI(title="MCP RAG API", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(KBError)
async def kb_error_handler(_request: Request, exc: KBError) -> JSONResponse:
    status = 404 if isinstance(exc, NotFound) else 403 if isinstance(exc, PermissionDenied) else 400
    return JSONResponse(status_code=status, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Loga 500s não tratados com o request-id e responde JSON genérico.

    Este handler roda no ServerErrorMiddleware (fora do RequestIdMiddleware), então o
    request-id vem do scope e o header precisa ser colocado na resposta aqui.
    """
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        request_id_ctx.set(request_id)
    logger.exception(
        "erro 500 não tratado (request_id=%s) em %s %s: %s", request_id, request.method, request.url.path, exc
    )
    headers = {"X-Request-Id": request_id} if request_id else None
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor."}, headers=headers)


class RequestIdMiddleware:
    """Gera um uuid por request, devolve no header X-Request-Id e inclui nos logs."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_ctx.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).append("X-Request-Id", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_ctx.reset(token)


app.add_middleware(RequestIdMiddleware)


class RequireApiKey:
    """Barra o /mcp inteiro (inclusive initialize e list_tools) sem a chave do .env.

    Cada tool ainda confere escopos no Principal; isto é só o portão, para que um servidor
    exposto na internet não revele nem a lista de tools a quem não tem chave.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not get_settings().kb_auth_disabled:
            headers = dict(scope["headers"])
            token = bearer_token(headers.get(b"authorization", b"").decode())
            valid = False
            if token:
                try:
                    resolve_env_key(token)
                    valid = True
                except PermissionDenied:
                    pass
            if not valid:
                response = JSONResponse(
                    {"detail": "Chave de API ausente ou inválida."},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# Montado por último: as rotas REST têm prioridade; /mcp cai no app do MCP.
app.mount("/", RequireApiKey(mcp_app))
