from mcp_rag_api.core.chunking import chunk_text, content_hash, normalize


def test_normalize_collapses_whitespace():
    assert normalize("a  \t b\r\n\n\n\nc ") == "a b\n\nc"


def test_short_text_is_single_chunk():
    chunks = chunk_text("Olá mundo.\n\nSegundo parágrafo.", max_words=50, overlap_words=5)
    assert len(chunks) == 1
    assert chunks[0].content == "Olá mundo.\n\nSegundo parágrafo."
    assert chunks[0].word_count == 4


def test_long_text_is_split_with_overlap_and_size_limit():
    paragraphs = [" ".join(f"p{i}w{j}" for j in range(40)) for i in range(10)]
    chunks = chunk_text("\n\n".join(paragraphs), max_words=100, overlap_words=10)
    assert len(chunks) > 1
    assert all(c.word_count <= 100 for c in chunks)
    # a sobreposição repete o fim de um chunk no começo do seguinte
    tail = chunks[0].content.split()[-1]
    assert tail in chunks[1].content.split()
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_giant_paragraph_is_split():
    chunks = chunk_text(" ".join(["x"] * 1000), max_words=300, overlap_words=0)
    assert sum(c.word_count for c in chunks) == 1000


def test_empty_text():
    assert chunk_text("   \n\n  ") == []


def test_giant_paragraph_slice_never_gets_paragraph_separator():
    # Corte mid-parágrafo com overlap: a fatia que continua o parágrafo gigante
    # deve ser unida por espaço simples, não por "\n\n" no meio da frase.
    para = " ".join(f"w{i}" for i in range(500))
    chunks = chunk_text(para, max_words=450, overlap_words=60)
    assert [c.word_count for c in chunks] == [450, 110]
    assert "\n\n" not in chunks[1].content
    # o overlap repete o fim da fatia anterior
    assert chunks[1].content.startswith(" ".join(f"w{i}" for i in range(390, 450)))


def test_paragraph_break_inside_overlap_is_preserved():
    # Overlap que cruza a fronteira entre dois parágrafos reais mantém a quebra "\n\n".
    paragraphs = [" ".join(f"p{i}w{j}" for j in range(20)) for i in range(6)]
    chunks = chunk_text("\n\n".join(paragraphs), max_words=30, overlap_words=15)
    assert len(chunks) > 1
    joined = "\n\n".join(paragraphs)
    for c in chunks:
        if "\n\n" in c.content:
            before, after = c.content.split("\n\n", 1)
            assert before + "\n\n" + after in joined


def test_word_count_matches_content_and_never_exceeds_limit():
    # Muitos parágrafos pequenos => várias quebras "\n\n" por chunk: a contagem de
    # limite e o word_count reportado precisam coincidir com o texto final.
    paragraphs = [" ".join(f"p{i}w{j}" for j in range(37)) for i in range(12)]
    chunks = chunk_text("\n\n".join(paragraphs), max_words=100, overlap_words=10)
    assert len(chunks) > 1
    for c in chunks:
        assert c.word_count == len(c.content.split())
        assert c.word_count <= 100


def test_size_limit_counts_words_not_paragraph_breaks():
    # O limite é de palavras: 150 * 3 = 450 cabe num chunk só — as quebras "\n\n"
    # entre parágrafos não podem roubar a vaga de palavras reais.
    paragraphs = [" ".join(f"p{i}w{j}" for j in range(150)) for i in range(3)]
    chunks = chunk_text("\n\n".join(paragraphs), max_words=450, overlap_words=0)
    assert len(chunks) == 1
    assert chunks[0].word_count == 450


def test_content_hash_changes_with_title():
    assert content_hash("a", "x") != content_hash("b", "x")
