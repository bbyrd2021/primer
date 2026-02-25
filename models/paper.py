# models/paper.py
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
    relevance_score: int | None = Field(None, ge=1, le=5)
    tier: int | None = Field(None, ge=1, le=3)


class UploadResponse(BaseModel):
    session_id: str
    papers: list[PaperCard]
    total_papers: int
    total_chunks: int
