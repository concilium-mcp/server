import pytest
from pydantic import ValidationError

from mcp_rag_api.config import EMBEDDING_DIM, Settings


def test_embedding_dim_positiva():
    assert EMBEDDING_DIM > 0


def test_defaults_sao_validos():
    s = Settings()
    assert s.chunk_overlap_words < s.chunk_words
    assert 0.0 <= s.duplicate_threshold <= 1.0
    assert 0.0 <= s.memory_duplicate_threshold <= 1.0
    assert s.kb_log_level == "INFO"


@pytest.mark.parametrize("overlap", [450, 500])
def test_overlap_maior_ou_igual_ao_chunk_rejeitado(overlap):
    with pytest.raises(ValidationError):
        Settings(chunk_words=450, chunk_overlap_words=overlap)


@pytest.mark.parametrize("campo", ["duplicate_threshold", "memory_duplicate_threshold"])
@pytest.mark.parametrize("valor", [-0.1, 1.01])
def test_threshold_fora_de_0_a_1_rejeitado(campo, valor):
    with pytest.raises(ValidationError):
        Settings(**{campo: valor})
