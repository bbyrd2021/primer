# tests/test_main.py
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from models.message import ChatResponse
from models.paper import PaperCard, UploadResponse

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ANT_KEY = "sk-ant-api03-testkey"
VALID_OAI_KEY = "sk-proj-testkey"

DUMMY_CARD = PaperCard(filename="test.pdf", session_id="sess-123")
DUMMY_UPLOAD_RESPONSE = UploadResponse(
    session_id="sess-123",
    papers=[DUMMY_CARD],
    total_papers=1,
    total_chunks=5,
)
DUMMY_CHAT_RESPONSE = ChatResponse(
    content="Answer text",
    sources=["test.pdf"],
    chunks_retrieved=3,
)


def _make_pdf_form(key: str = VALID_ANT_KEY):
    """Return (files, data, headers) suitable for a /api/upload POST."""
    pdf_bytes = b"%PDF-1.4 minimal fake pdf"
    files = {"files": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"research_question": "What is the methodology?"}
    headers = {"X-LLM-Key": key}
    return files, data, headers


# ---------------------------------------------------------------------------
# POST /api/upload — key validation
# ---------------------------------------------------------------------------


def test_upload_missing_key_returns_400():
    pdf_bytes = b"%PDF-1.4 minimal"
    response = client.post(
        "/api/upload",
        files={"files": ("t.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"research_question": "question"},
    )
    assert response.status_code == 400


def test_upload_invalid_key_returns_400():
    pdf_bytes = b"%PDF-1.4 minimal"
    response = client.post(
        "/api/upload",
        files={"files": ("t.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"research_question": "question"},
        headers={"X-LLM-Key": "garbage-key"},
    )
    assert response.status_code == 400


def test_upload_valid_anthropic_key_calls_process(tmp_path):
    files, data, headers = _make_pdf_form(VALID_ANT_KEY)

    async def fake_process(file, rq, session_id, session_dir, api_key=""):
        return DUMMY_CARD, 5

    with patch("main._process_single_file", side_effect=fake_process):
        response = client.post(
            "/api/upload", files=files, data=data, headers=headers
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total_papers"] == 1


def test_upload_valid_openai_key_calls_process(tmp_path):
    files, data, headers = _make_pdf_form(VALID_OAI_KEY)

    async def fake_process(file, rq, session_id, session_dir, api_key=""):
        return DUMMY_CARD, 3

    with patch("main._process_single_file", side_effect=fake_process):
        response = client.post(
            "/api/upload", files=files, data=data, headers=headers
        )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/chat — key validation
# ---------------------------------------------------------------------------


def test_chat_missing_key_returns_400():
    response = client.post(
        "/api/chat",
        json={
            "session_id": "sess",
            "message": "hello",
            "research_question": "rq",
            "paper_count": 1,
        },
    )
    assert response.status_code == 400


def test_chat_invalid_key_returns_400():
    response = client.post(
        "/api/chat",
        json={
            "session_id": "sess",
            "message": "hello",
            "research_question": "rq",
            "paper_count": 1,
        },
        headers={"X-LLM-Key": "bad-key"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/chat/stream — key validation + SSE content type
# ---------------------------------------------------------------------------


def test_chat_stream_missing_key_returns_400():
    response = client.post(
        "/api/chat/stream",
        json={
            "session_id": "sess",
            "message": "hello",
            "research_question": "rq",
            "paper_count": 1,
        },
    )
    assert response.status_code == 400


def test_chat_stream_invalid_key_returns_400():
    response = client.post(
        "/api/chat/stream",
        json={
            "session_id": "sess",
            "message": "hello",
            "research_question": "rq",
            "paper_count": 1,
        },
        headers={"X-LLM-Key": "not-a-real-key"},
    )
    assert response.status_code == 400


def test_chat_stream_valid_key_returns_sse():
    async def fake_stream_chat(**kwargs):
        yield 'data: {"type": "chunk", "text": "hi"}\n\n'
        yield 'data: {"type": "done", "sources": [], "chunks_retrieved": 0}\n\n'

    with patch("main.stream_chat", side_effect=fake_stream_chat):
        response = client.post(
            "/api/chat/stream",
            json={
                "session_id": "sess",
                "message": "hello",
                "research_question": "rq",
                "paper_count": 1,
            },
            headers={"X-LLM-Key": VALID_ANT_KEY},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
