import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.config import get_settings
from app.models import QueryRequest, QueryResponse, SourceChunk
from app.rate_limit import limiter
from app.services.grounding import compute_grounding_score
from app.services.llm import generate_answer, generate_answer_stream
from app.services.vectorstore import query_user_documents

router = APIRouter(prefix="/query", tags=["query"])
logger = logging.getLogger("query")
settings = get_settings()


@router.post("", response_model=QueryResponse)
@limiter.limit(settings.RATE_LIMIT_QUERY)
async def query_documents(
    request: Request,
    payload: QueryRequest,
    user: dict = Depends(get_current_user),
):
    results = query_user_documents(user["uid"], payload.question, top_k=payload.top_k)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        raise HTTPException(
            status_code=404,
            detail="No documents found for your account. Upload a document first.",
        )

    try:
        answer = generate_answer(payload.question, documents)
    except Exception:
        logger.exception("Answer generation failed for user %s", user["uid"])
        raise HTTPException(status_code=502, detail="Answer generation failed. Please try again.")

    confidence = compute_grounding_score(distances)

    sources = [
        SourceChunk(
            filename=meta.get("filename", "unknown"),
            page=meta.get("page"),
            excerpt=doc[:280],
            score=round(1 - dist, 4),  # convert distance to a similarity-style score
        )
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]

    return QueryResponse(answer=answer, confidence=confidence, sources=sources)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/stream")
@limiter.limit(settings.RATE_LIMIT_QUERY)
async def query_documents_stream(
    request: Request,
    payload: QueryRequest,
    user: dict = Depends(get_current_user),
):
    """
    Server-Sent Events version of /query. Emits, in order:
    1. one "meta" event with sources + confidence (computed from
       retrieval, available before generation starts)
    2. a stream of "token" events as the answer is generated
    3. a final "done" event, or an "error" event if generation fails
       partway through
    """
    results = query_user_documents(user["uid"], payload.question, top_k=payload.top_k)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        raise HTTPException(
            status_code=404,
            detail="No documents found for your account. Upload a document first.",
        )

    confidence = compute_grounding_score(distances)
    sources = [
        {
            "filename": meta.get("filename", "unknown"),
            "page": meta.get("page"),
            "excerpt": doc[:280],
            "score": round(1 - dist, 4),
        }
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]

    def event_generator():
        yield _sse({"type": "meta", "confidence": confidence, "sources": sources})
        try:
            for delta in generate_answer_stream(payload.question, documents):
                yield _sse({"type": "token", "text": delta})
        except Exception:  # noqa: BLE001 - log full detail server-side, don't leak it to the client
            logger.exception("Streaming generation failed for user %s", user["uid"])
            yield _sse({"type": "error", "message": "Answer generation failed. Please try again."})
            return
        yield _sse({"type": "done"})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
