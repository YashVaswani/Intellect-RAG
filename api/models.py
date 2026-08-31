# api/models.py
"""
Pydantic models for API request/response schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional


# ─── Chat ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    session_id: str
    model: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    search_query: str
    sources: list[dict] = []
    source_type: str
    confidence_score: float
    model_used: str
    token_usage: dict = {}
    token_display: str = ""
    elapsed: float = 0.0
    cached: bool = False
    timestamp: Optional[str] = None


# ─── Sessions ────────────────────────────────────────────────

class SessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class SessionResponse(BaseModel):
    id: str
    title: str
    pinned: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0


# ─── Documents ───────────────────────────────────────────────

class DocumentInfo(BaseModel):
    name: str
    chunk_count: int = 0
    file_type: str = ""
    ingested_at: Optional[str] = None


class CollectionStats(BaseModel):
    total_vectors: int = 0
    total_documents: int = 0
    collection_name: str = ""
