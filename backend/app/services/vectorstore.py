"""
Chroma Cloud client wrapper.

Isolation principle: every chunk is written with metadata
{"user_id": <firebase uid>, ...}. Every query passes a `where`
filter on user_id from the verified token - never from client input.
Chroma Cloud is a drop-in replacement for local ChromaDB that avoids
the local-disk-doesn't-persist problem on free hosting tiers.
"""
import uuid

import chromadb
import numpy as np

from app.config import get_settings

settings = get_settings()

_client = chromadb.CloudClient(
    tenant=settings.CHROMA_TENANT,
    database=settings.CHROMA_DATABASE,
    api_key=settings.CHROMA_API_KEY,
)

_collection = _client.get_or_create_collection(name=settings.CHROMA_COLLECTION)


def add_chunks(
    user_id: str,
    filename: str,
    chunks: list[str],
    page_numbers: list[int | None],
) -> int:
    if not chunks:
        return 0

    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [
        {
            "user_id": user_id,
            "filename": filename,
            "page": page_numbers[i] if i < len(page_numbers) else None,
        }
        for i in range(len(chunks))
    ]

    _collection.add(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-8
    return float(np.dot(a, b) / denom)


def _mmr_select(
    query_embedding: np.ndarray,
    candidate_embeddings: list[np.ndarray],
    top_k: int,
    lambda_mult: float,
) -> list[int]:
    """
    Maximal Marginal Relevance: greedily picks the candidate that
    balances relevance to the query against redundancy with what's
    already been selected. Returns indices into candidate_embeddings,
    in selection order. This addresses the "top-k scores cluster too
    closely together" ambiguity problem by actively spreading picks
    across distinct chunks instead of returning near-duplicates.
    """
    if not candidate_embeddings:
        return []

    relevance = [_cosine_similarity(query_embedding, c) for c in candidate_embeddings]
    selected: list[int] = []
    remaining = list(range(len(candidate_embeddings)))

    while remaining and len(selected) < top_k:
        best_idx, best_score = None, float("-inf")
        for idx in remaining:
            redundancy = max(
                (_cosine_similarity(candidate_embeddings[idx], candidate_embeddings[j]) for j in selected),
                default=0.0,
            )
            mmr_score = lambda_mult * relevance[idx] - (1 - lambda_mult) * redundancy
            if mmr_score > best_score:
                best_score, best_idx = mmr_score, idx
        selected.append(best_idx)
        remaining.remove(best_idx)

    return selected


def query_user_documents(user_id: str, question: str, top_k: int = 5) -> dict:
    """
    Runs similarity search scoped to this user's chunks only.
    The `where={"user_id": user_id}` filter is the isolation boundary -
    user_id here always comes from the verified auth token upstream.

    Two extra passes on top of raw similarity search:
    1. Score threshold - candidates weaker than SCORE_DISTANCE_THRESHOLD
       are dropped rather than passed to the LLM as if they were relevant.
    2. MMR reranking - pulls a wider candidate pool (MMR_FETCH_K), then
       reranks for a mix of relevance and diversity so near-duplicate
       chunks don't crowd out genuinely different ones when top-k
       scores are clustered close together.
    """
    fetch_k = max(settings.MMR_FETCH_K, top_k) if settings.MMR_ENABLED else top_k

    raw = _collection.query(
        query_texts=[question],
        n_results=fetch_k,
        where={"user_id": user_id},
        include=["documents", "metadatas", "distances", "embeddings"],
    )

    documents = raw.get("documents", [[]])[0]
    metadatas = raw.get("metadatas", [[]])[0]
    distances = raw.get("distances", [[]])[0]
    embeddings = raw.get("embeddings", [[]])[0]

    # Score threshold: drop weak matches outright
    kept = [i for i in range(len(documents)) if distances[i] <= settings.SCORE_DISTANCE_THRESHOLD]
    if not kept:
        # nothing clears the bar - fall back to the single closest match
        # so the caller still gets something rather than an empty result
        kept = [0] if documents else []

    if not settings.MMR_ENABLED or not embeddings or len(kept) <= top_k:
        final_idx = kept[:top_k]
    else:
        query_embedding = _collection._embedding_function([question])[0]
        query_embedding = np.array(query_embedding)
        candidate_embeddings = [np.array(embeddings[i]) for i in kept]
        mmr_order = _mmr_select(query_embedding, candidate_embeddings, top_k, settings.MMR_LAMBDA)
        final_idx = [kept[i] for i in mmr_order]

    return {
        "documents": [[documents[i] for i in final_idx]],
        "metadatas": [[metadatas[i] for i in final_idx]],
        "distances": [[distances[i] for i in final_idx]],
    }


def delete_user_document(user_id: str, filename: str) -> None:
    # Chroma requires $and for multi-field where clauses
    _collection.delete(
        where={"$and": [{"user_id": user_id}, {"filename": filename}]}
    )
