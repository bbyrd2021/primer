# tests/test_synthesize.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.synthesize import chat, generate_brief, stream_chat, stream_brief
from models.message import ChatResponse


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SAMPLE_CHUNKS = [
    {"source": "paper1.pdf", "text": "Chunk from paper 1.", "page": 1},
    {"source": "paper2.pdf", "text": "Chunk from paper 2.", "page": 3},
]


async def _collect_sse(gen) -> list[dict]:
    """Collect all SSE events from an async generator into a list of dicts."""
    events = []
    async for line in gen:
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


# ---------------------------------------------------------------------------
# chat()
# ---------------------------------------------------------------------------


def test_chat_no_chunks_returns_fallback():
    with patch("core.synthesize.retrieve", return_value=[]):
        result = chat(
            message="Any question",
            session_id="sess",
            research_question="rq",
            paper_count=0,
            history=[],
            api_key="sk-ant-test",
        )

    assert isinstance(result, ChatResponse)
    assert result.sources == []
    assert result.chunks_retrieved == 0
    assert "don't see anything" in result.content


def test_chat_with_chunks_calls_complete():
    with patch("core.synthesize.retrieve", return_value=SAMPLE_CHUNKS):
        with patch("core.synthesize.complete", return_value="Synthesized answer") as mock_complete:
            result = chat(
                message="Question",
                session_id="sess",
                research_question="rq",
                paper_count=2,
                history=[],
                api_key="sk-ant-test",
            )

    mock_complete.assert_called_once()
    call_kwargs = mock_complete.call_args[1]
    assert call_kwargs["api_key"] == "sk-ant-test"

    assert result.content == "Synthesized answer"
    assert set(result.sources) == {"paper1.pdf", "paper2.pdf"}
    assert result.chunks_retrieved == 2


# ---------------------------------------------------------------------------
# generate_brief()
# ---------------------------------------------------------------------------


def test_generate_brief_no_chunks_returns_fallback():
    with patch("core.synthesize.retrieve", return_value=[]):
        result = generate_brief(
            research_question="rq",
            session_id="sess",
            api_key="sk-ant-test",
        )

    assert result.sources == []
    assert result.chunks_retrieved == 0
    assert "No relevant content" in result.content


def test_generate_brief_with_chunks_calls_complete_with_brief_max_tokens():
    from core.llm import BRIEF_MAX_TOKENS

    with patch("core.synthesize.retrieve", return_value=SAMPLE_CHUNKS):
        with patch("core.synthesize.complete", return_value="Brief text") as mock_complete:
            result = generate_brief(
                research_question="rq",
                session_id="sess",
                api_key="sk-ant-test",
            )

    mock_complete.assert_called_once()
    call_kwargs = mock_complete.call_args[1]
    assert call_kwargs["max_tokens"] == BRIEF_MAX_TOKENS
    assert call_kwargs["api_key"] == "sk-ant-test"

    assert result.content == "Brief text"
    assert result.chunks_retrieved == 2


# ---------------------------------------------------------------------------
# stream_chat()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_chat_no_chunks():
    with patch("core.synthesize.retrieve", return_value=[]):
        events = await _collect_sse(
            stream_chat(
                message="q",
                session_id="sess",
                research_question="rq",
                paper_count=0,
                history=[],
                api_key="sk-ant-test",
            )
        )

    types = [e["type"] for e in events]
    assert "chunk" in types
    assert types[-1] == "done"
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["sources"] == []
    assert done_event["chunks_retrieved"] == 0


@pytest.mark.asyncio
async def test_stream_chat_with_chunks():
    stream_texts = ["Hello", " world"]

    async def fake_stream_complete(**kwargs):
        for t in stream_texts:
            yield t

    with patch("core.synthesize.retrieve", return_value=SAMPLE_CHUNKS):
        with patch("core.synthesize.stream_complete", side_effect=fake_stream_complete):
            events = await _collect_sse(
                stream_chat(
                    message="q",
                    session_id="sess",
                    research_question="rq",
                    paper_count=2,
                    history=[],
                    api_key="sk-ant-test",
                )
            )

    chunk_events = [e for e in events if e["type"] == "chunk"]
    assert [e["text"] for e in chunk_events] == stream_texts

    done_event = next(e for e in events if e["type"] == "done")
    assert set(done_event["sources"]) == {"paper1.pdf", "paper2.pdf"}
    assert done_event["chunks_retrieved"] == 2


# ---------------------------------------------------------------------------
# stream_brief()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_brief_no_chunks():
    with patch("core.synthesize.retrieve", return_value=[]):
        events = await _collect_sse(
            stream_brief(
                research_question="rq",
                session_id="sess",
                api_key="sk-ant-test",
            )
        )

    types = [e["type"] for e in events]
    assert "chunk" in types
    assert types[-1] == "done"
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["sources"] == []


@pytest.mark.asyncio
async def test_stream_brief_with_chunks():
    stream_texts = ["Brief", " content"]

    async def fake_stream_complete(**kwargs):
        for t in stream_texts:
            yield t

    with patch("core.synthesize.retrieve", return_value=SAMPLE_CHUNKS):
        with patch("core.synthesize.stream_complete", side_effect=fake_stream_complete):
            events = await _collect_sse(
                stream_brief(
                    research_question="rq",
                    session_id="sess",
                    api_key="sk-ant-test",
                )
            )

    chunk_events = [e for e in events if e["type"] == "chunk"]
    assert [e["text"] for e in chunk_events] == stream_texts

    done_event = next(e for e in events if e["type"] == "done")
    assert set(done_event["sources"]) == {"paper1.pdf", "paper2.pdf"}
