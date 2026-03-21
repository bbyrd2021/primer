# models/paper.py
from datetime import datetime

from pydantic import BaseModel, Field


class PaperCard(BaseModel):
    # Identity
    filename: str
    session_id: str
    error: bool = False

    # Extracted fields
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    year: int | None = None
    task: str | None = None
    modality: str | None = None
    methodology: str | None = None
    results: str | None = None
    datasets: list[str] = Field(default_factory=list)
    pretraining: str | None = None
    code_available: bool = False
    code_url: str | None = None
    key_limitations: str | None = None
    synthesis_note: str | None = None

    # Scoring
    relevance_score: int | None = Field(default=None, ge=1, le=5)
    tier: int | None = Field(default=None, ge=1, le=3)


class UploadResponse(BaseModel):
    session_id: str
    papers: list[PaperCard]
    total_papers: int
    total_chunks: int


class SessionMeta(BaseModel):
    session_id: str
    research_question: str
    created_at: datetime
    paper_count: int = 0
    updated_at: datetime | None = None
    user_id: str | None = None


class SessionMetaPublic(BaseModel):
    """SessionMeta without user_id — safe to return in API responses."""

    session_id: str
    research_question: str
    created_at: datetime
    paper_count: int = 0
    updated_at: datetime | None = None


class UpdateSessionRequest(BaseModel):
    research_question: str = Field(..., min_length=1, max_length=2000)
