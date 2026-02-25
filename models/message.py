# models/message.py
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=4000)
    research_question: str = Field(..., min_length=1)
    paper_count: int = Field(..., ge=0)
    history: list[dict] = Field(default_factory=list)
    generate_brief: bool = False


class ChatResponse(BaseModel):
    content: str
    sources: list[str]
    chunks_retrieved: int
