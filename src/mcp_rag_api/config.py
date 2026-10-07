from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Dimensão fixa do vetor no schema (migrations/001_init.sql). Todos os provedores são configurados para ela.
EMBEDDING_DIM = 1024
if EMBEDDING_DIM <= 0:
    raise ValueError("EMBEDDING_DIM deve ser positiva")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://user:password@localhost:5432/kb"
    migrations_dir: Path = PROJECT_ROOT / "migrations"

    embedding_provider: Literal["voyage", "openai", "local", "fake"] = "voyage"
    embedding_model: str = ""
    voyage_api_key: str = ""
    openai_api_key: str = ""

    chunk_words: int = 450
    chunk_overlap_words: int = 60

    duplicate_threshold: float = 0.92
    memory_duplicate_threshold: float = 0.90
    load_agent_memory_limit: int = 15

    kb_api_key: str = ""
    kb_auth_disabled: bool = False
    kb_log_level: str = "INFO"

    @field_validator("duplicate_threshold", "memory_duplicate_threshold")
    @classmethod
    def _thresholds_entre_0_e_1(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("threshold de duplicata deve estar em [0, 1]")
        return v

    @model_validator(mode="after")
    def _chunk_sem_conflito(self) -> "Settings":
        # Sem isso, chunk_text explodiria com ValueError no meio de uma requisição (500).
        if self.chunk_overlap_words >= self.chunk_words:
            raise ValueError("CHUNK_OVERLAP_WORDS deve ser menor que CHUNK_WORDS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
