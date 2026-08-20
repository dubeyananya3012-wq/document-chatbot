from typing import Literal, Optional
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    filename: str
    status: Literal["success", "failed"]
    chunk_count: int
    error: Optional[str] = None


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class SourceChunk(BaseModel):
    filename: str
    page: Optional[int] = None
    excerpt: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    confidence: Literal["high", "medium", "low"]
    sources: list[SourceChunk]


class UploadHistoryEntry(BaseModel):
    filename: str
    uploader: str
    timestamp: str
    chunk_count: int
    status: Literal["success", "failed"]
