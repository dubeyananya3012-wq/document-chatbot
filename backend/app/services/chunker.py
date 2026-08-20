"""
Chunking strategies: recursive, token, character, sentence, hybrid,
semantic. Hybrid is the default (structure-aware: splits on markdown
headers/tables first, then falls back to recursive character splitting
within each section). Semantic is implemented but not yet benchmarked
against hybrid for answer quality - see PRD open problems.
"""
import re
from dataclasses import dataclass

from app.config import get_settings
from app.services.token_check import enforce_token_ceiling

settings = get_settings()


@dataclass
class Chunk:
    text: str
    page_number: int | None


def _recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    separators = ["\n\n", "\n", ". ", " "]
    return _split_with_separators(text, separators, chunk_size, overlap)


def _split_with_separators(text: str, separators: list[str], chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size or not separators:
        return [text] if text.strip() else []

    sep, rest_seps = separators[0], separators[1:]
    parts = text.split(sep)

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = current + sep + part if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = part

    if current:
        chunks.append(current)

    # Recurse into any chunk that's still too big
    final: list[str] = []
    for c in chunks:
        if len(c) > chunk_size and rest_seps:
            final.extend(_split_with_separators(c, rest_seps, chunk_size, overlap))
        else:
            final.append(c)

    # Apply overlap by prepending the tail of the previous chunk
    if overlap > 0:
        overlapped = []
        for i, c in enumerate(final):
            if i == 0:
                overlapped.append(c)
            else:
                tail = final[i - 1][-overlap:]
                overlapped.append(tail + c)
        return overlapped

    return final


def _token_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    step = max(chunk_size - overlap, 1)
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), step)]


def _character_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    step = max(chunk_size - overlap, 1)
    return [text[i:i + chunk_size] for i in range(0, len(text), step)]


def _sentence_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""
    for s in sentences:
        candidate = f"{current} {s}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = s
    if current:
        chunks.append(current)
    return chunks


def _hybrid_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split on markdown structure (headers, tables) first, then
    recursive-split any section that's still oversized."""
    sections = re.split(r"(?=^#{1,6}\s)", text, flags=re.MULTILINE)
    chunks: list[str] = []
    for section in sections:
        if not section.strip():
            continue
        if len(section) <= chunk_size:
            chunks.append(section.strip())
        else:
            chunks.extend(_recursive_split(section, chunk_size, overlap))
    return chunks


def _semantic_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Groups sentences by paragraph boundary as a proxy for topic
    boundaries. Not yet benchmarked against hybrid - see PRD open
    problems before relying on this for production answer quality.
    """
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for p in paragraphs:
        candidate = f"{current}\n\n{p}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = p
    if current:
        chunks.append(current)
    return chunks


_STRATEGIES = {
    "recursive": _recursive_split,
    "token": _token_split,
    "character": _character_split,
    "sentence": _sentence_split,
    "hybrid": _hybrid_split,
    "semantic": _semantic_split,
}


def chunk_text(
    text: str,
    strategy: str | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    strategy = strategy or settings.CHUNK_STRATEGY
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    if strategy not in _STRATEGIES:
        raise ValueError(f"Unknown chunk strategy: {strategy}")

    raw_chunks = _STRATEGIES[strategy](text, chunk_size, overlap)
    raw_chunks = [c for c in raw_chunks if c.strip()]

    # Token-ceiling safeguard applies regardless of strategy
    return enforce_token_ceiling(raw_chunks)
