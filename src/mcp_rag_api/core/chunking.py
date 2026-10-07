"""Quebra de texto em chunks por palavras, respeitando parágrafos quando possível."""

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    index: int
    content: str
    word_count: int


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def content_hash(title: str, content: str) -> str:
    return hashlib.sha256(f"{title}\n\n{content}".encode()).hexdigest()


def _word_count(items: list[str]) -> int:
    return sum(1 for w in items if w != "\n\n")


def _overlap_tail(items: list[str], overlap_words: int) -> list[str]:
    """Últimas `overlap_words` palavras de `items`, preservando quebras de parágrafo internas."""
    if not overlap_words:
        return []
    tail: list[str] = []
    for item in reversed(items):
        tail.append(item)
        if _word_count(tail) >= overlap_words:
            break
    tail.reverse()
    return tail


def chunk_text(text: str, max_words: int = 450, overlap_words: int = 60) -> list[Chunk]:
    if overlap_words >= max_words:
        raise ValueError("overlap_words deve ser menor que max_words")
    text = normalize(text)
    if not text:
        return []

    # Unidades = parágrafos (flag starts_paragraph marca quebra real); parágrafos gigantes
    # são quebrados em fatias de max_words, mas só a primeira fatia inicia parágrafo novo.
    units: list[tuple[list[str], bool]] = []
    for para in text.split("\n\n"):
        words = para.split(" ")
        for i in range(0, len(words), max_words):
            units.append((words[i : i + max_words], i == 0))

    chunks: list[list[str]] = []
    current: list[str] = []
    for words, starts_paragraph in units:
        if current and _word_count(current) + len(words) > max_words:
            chunks.append(current)
            current = _overlap_tail(current, overlap_words)
            if _word_count(current) + len(words) > max_words:
                current = []
        if current:
            # Quebra de parágrafo real só quando a unidade inicia um parágrafo novo;
            # fatias do mesmo parágrafo gigante continuam unidas por espaço simples.
            current = current + (["\n\n"] if starts_paragraph else []) + words
        else:
            current = list(words)
    if current:
        chunks.append(current)

    out: list[Chunk] = []
    for i, words in enumerate(chunks):
        content = " ".join(words).replace(" \n\n ", "\n\n").strip()
        out.append(Chunk(index=i, content=content, word_count=_word_count(words)))
    return out
