"""Identidade (Principal), escopos e autenticação pelas chaves do .env (KB_API_KEY e KB_READ_ONLY_KEY).

Escopos:
  read           consultar a base e o próprio agente (perfil, memórias, sessões, tarefas)
  write          inserir/atualizar documentos, memórias, sessões e tarefas (implica read)
  agents:manage  cadastrar/configurar agentes, aprovar propostas, ligar autonomia
  admin          tudo
"""

import hmac
from dataclasses import dataclass, field
from uuid import UUID

from .config import get_settings

VALID_SCOPES = {"read", "write", "agents:manage", "admin"}
_IMPLIES = {"write": {"read"}, "agents:manage": {"read"}}


class KBError(Exception):
    """Erro esperado, com mensagem para o agente/usuário."""


class PermissionDenied(KBError):
    pass


class Unauthenticated(KBError):
    """Credencial ausente ou inválida (HTTP 401), distinta de escopo insuficiente (403)."""


class NotFound(KBError):
    pass


@dataclass(frozen=True)
class Principal:
    actor: str
    scopes: frozenset[str]
    agent_id: UUID | None = None
    agent_slug: str | None = None
    allowed_collections: tuple[str, ...] = field(default_factory=tuple)  # vazio = todas

    def has(self, scope: str) -> bool:
        if "admin" in self.scopes or scope in self.scopes:
            return True
        return any(scope in _IMPLIES.get(s, ()) for s in self.scopes)

    def require(self, scope: str) -> None:
        if not self.has(scope):
            raise PermissionDenied(f"Esta chave não tem o escopo '{scope}'.")

    @property
    def is_manager(self) -> bool:
        return self.has("agents:manage")

    def can_access_collection(self, name: str) -> bool:
        return not self.allowed_collections or name in self.allowed_collections

    def require_collection(self, name: str) -> None:
        if not self.can_access_collection(name):
            raise PermissionDenied(f"Sem acesso à coleção '{name}'.")

    def collection_filter(self, requested: list[str] | None) -> list[str] | None:
        """Coleções efetivas para uma busca: pedido ∩ permitido (None = sem filtro)."""
        if requested:
            for name in requested:
                self.require_collection(name)
            return requested
        return list(self.allowed_collections) or None


DEV_PRINCIPAL = Principal(actor="dev", scopes=frozenset({"admin"}))


def validate_scopes(scopes: list[str]) -> list[str]:
    invalid = set(scopes) - VALID_SCOPES
    if invalid:
        raise KBError(f"Escopos inválidos: {sorted(invalid)}. Válidos: {sorted(VALID_SCOPES)}")
    return sorted(set(scopes))


def resolve_env_key(token: str) -> Principal:
    """Valida o Bearer token contra KB_API_KEY (comparação em tempo constante, sem query no banco)."""
    expected = get_settings().kb_api_key
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        raise Unauthenticated("Chave de API inválida.")
    return Principal(actor="env:kb_api_key", scopes=frozenset({"admin"}))


def resolve_read_only_key(token: str) -> Principal:
    """Valida o Bearer token contra KB_READ_ONLY_KEY (opcional): credencial genuinamente só de leitura."""
    expected = get_settings().kb_read_only_key
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        raise Unauthenticated("Chave de API inválida.")
    return Principal(actor="env:kb_read_only_key", scopes=frozenset({"read"}))


def resolve_api_key(token: str) -> Principal:
    """Aceita a chave admin (KB_API_KEY) ou a read-only (KB_READ_ONLY_KEY)."""
    try:
        return resolve_env_key(token)
    except Unauthenticated:
        return resolve_read_only_key(token)


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None
