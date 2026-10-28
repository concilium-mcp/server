"""Import de arquivos soltos pela API REST (plan-server-10): POST /documents/upload, síncrono.

Coleções com prefixo "fi-" (o banco é compartilhado entre os módulos de integração).
O TestClient roda o lifespan no loop do portal dele, então cada teste fecha o pool da
sessão antes e o recria ao final (mesmo padrão do test_http.py).
"""

import pytest
from fastapi.testclient import TestClient

from mcp_rag_api import db
from mcp_rag_api.config import get_settings
from mcp_rag_api.core import file_import

ADMIN = "chave-admin-teste"
READ_ONLY = "chave-somente-leitura"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("KB_API_KEY", ADMIN)
    monkeypatch.setenv("KB_READ_ONLY_KEY", READ_ONLY)
    monkeypatch.setenv("KB_AUTH_DISABLED", "false")
    get_settings.cache_clear()
    await db.close_pool()
    from mcp_rag_api.main import create_app

    with TestClient(create_app(), headers={"Authorization": f"Bearer {ADMIN}"}) as c:
        yield c
    await db.init_pool()
    get_settings.cache_clear()


def _collection(client: TestClient, name: str) -> str:
    r = client.post("/collections", json={"name": name})
    assert r.status_code == 200, r.text
    return name


def test_pdf_upload_becomes_searchable_document(client, make_pdf):
    col = _collection(client, "fi-pdf")
    pdf = make_pdf(["Politica de reembolso em 30 dias", "Contato pelo suporte"])
    r = client.post(
        "/documents/upload", data={"collection": col}, files={"file": ("Reembolso.pdf", pdf, "application/pdf")}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True and body["file_type"] == "pdf" and body["filename"] == "Reembolso.pdf"

    doc = client.get(f"/documents/{body['document_id']}").json()
    assert doc["title"] == "Reembolso"
    assert doc["external_id"] == "file:Reembolso.pdf"
    assert doc["source"] == "file-import"
    assert doc["metadata"]["pages"] == 2
    assert "Politica de reembolso em 30 dias" in doc["content"]

    hits = client.post("/search", json={"query": "Politica de reembolso em 30 dias", "collections": [col]}).json()
    assert any(h["document_id"] == body["document_id"] for h in hits)


def test_reupload_same_file_updates_instead_of_duplicating(client, make_docx, docx_p):
    col = _collection(client, "fi-docx")
    first = make_docx(docx_p("Contrato", style="Heading1") + docx_p("Prazo de 30 dias"))
    second = make_docx(docx_p("Contrato", style="Heading1") + docx_p("Prazo de 60 dias"))
    r1 = client.post("/documents/upload", data={"collection": col}, files={"file": ("contrato.docx", first, DOCX_MIME)})
    r2 = client.post(
        "/documents/upload", data={"collection": col}, files={"file": ("contrato.docx", second, DOCX_MIME)}
    )
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert r2.json()["document_id"] == r1.json()["document_id"]
    assert r2.json()["version"] == 2
    listed = client.get("/documents", params={"collection": col}).json()
    assert len(listed) == 1


def test_markdown_frontmatter_sets_title_and_tags(client):
    col = _collection(client, "fi-md")
    md = "---\ntitle: Ata de Reunião\ntags: [ata, comercial]\n---\n# Pauta\n\nItem 1\n".encode()
    r = client.post("/documents/upload", data={"collection": col}, files={"file": ("ata.md", md, "text/markdown")})
    assert r.status_code == 200, r.text
    doc = client.get(f"/documents/{r.json()['document_id']}").json()
    assert doc["title"] == "Ata de Reunião"
    assert sorted(doc["tags"]) == ["ata", "comercial"]


def test_bad_files_answer_400_with_the_reason(client, make_pdf):
    col = _collection(client, "fi-ruins")
    cases = [
        ("planilha.xlsx", b"x", "formato não suportado"),
        ("scan.pdf", make_pdf([""]), "escaneado"),
        ("quebrado.docx", b"nao sou um zip", "não foi possível ler"),
    ]
    for name, data, reason in cases:
        r = client.post("/documents/upload", data={"collection": col}, files={"file": (name, data)})
        assert r.status_code == 400, (name, r.text)
        assert reason in r.json()["detail"]


def test_upload_needs_write_scope(client):
    _collection(client, "fi-leitura")
    r = client.post(
        "/documents/upload",
        data={"collection": "fi-leitura"},
        files={"file": ("a.txt", b"texto")},
        headers={"Authorization": f"Bearer {READ_ONLY}"},
    )
    assert r.status_code == 403


def test_upload_body_limit_is_above_the_default(client, monkeypatch):
    # o limite geral (2 MB) não vale para o upload; acima do teto do arquivo, 413
    big = b"a" * (3 * 1024 * 1024)
    _collection(client, "fi-grande")
    r = client.post("/documents/upload", data={"collection": "fi-grande"}, files={"file": ("grande.txt", big)})
    assert r.status_code == 200, r.text
    monkeypatch.setattr(file_import, "MAX_FILE_BYTES", 1024)
    r = client.post("/documents/upload", data={"collection": "fi-grande"}, files={"file": ("grande2.txt", b"b" * 2048)})
    assert r.status_code == 413
    # outras rotas seguem com o limite geral
    r = client.post("/documents", json={"collection": "fi-grande", "title": "x", "content": "c" * (3 * 1024 * 1024)})
    assert r.status_code == 413
