"""
Token-count validation.

Every chunk is checked against MAX_CHUNK_TOKENS before embedding.
Oversized chunks are force-split with a smaller fallback splitter.
This guard exists because of a real production failure: a table-heavy
PDF produced a single chunk that exceeded the LLM's input token limit.
"""
import tiktoken

from app.config import get_settings

settings = get_settings()

_encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding.encode(text))


def enforce_token_ceiling(chunks: list[str]) -> list[str]:
    """
    Takes a list of chunk strings. Any chunk over MAX_CHUNK_TOKENS is
    force-split on whitespace boundaries into smaller pieces that each
    fit under the ceiling. Returns the corrected, flat list of chunks.
    """
    safe_chunks: list[str] = []
    for chunk in chunks:
        if count_tokens(chunk) <= settings.MAX_CHUNK_TOKENS:
            safe_chunks.append(chunk)
            continue
        safe_chunks.extend(_force_split(chunk))
    return safe_chunks


def _force_split(text: str) -> list[str]:
    """Fallback splitter: cuts on whitespace until each piece fits."""
    words = text.split()
    pieces: list[str] = []
    current: list[str] = []

    for word in words:
        current.append(word)
        candidate = " ".join(current)
        if count_tokens(candidate) >= settings.MAX_CHUNK_TOKENS:
            # back off the last word so we don't exceed the ceiling
            current.pop()
            if current:
                pieces.append(" ".join(current))
            current = [word]

    if current:
        pieces.append(" ".join(current))

    return pieces
