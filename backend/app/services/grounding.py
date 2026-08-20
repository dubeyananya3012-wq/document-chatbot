"""
Grounding score: high/medium/low confidence label instead of a binary
hallucination check. Computed from the similarity between the top
retrieved chunk distances and a simple length/overlap heuristic.

Chroma returns cosine *distances* (lower = more similar) for the
default embedding function. This is deliberately simple - it is a
first pass, not a substitute for a real faithfulness-scoring model.
"""
from typing import Literal

Confidence = Literal["high", "medium", "low"]


def compute_grounding_score(distances: list[float]) -> Confidence:
    """
    distances: the per-chunk distances returned by the vector store for
    the retrieved top-k results (lower distance = closer match).
    """
    if not distances:
        return "low"

    best = min(distances)

    # Thresholds are a starting point tuned for Chroma's default
    # sentence-transformer embedding space; revisit once semantic vs.
    # hybrid chunking is benchmarked (see PRD open problems).
    if best < 0.25:
        return "high"
    if best < 0.45:
        return "medium"
    return "low"
