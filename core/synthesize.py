# core/synthesize.py
import asyncio
import json
import logging
import os
from typing import AsyncIterator

import anthropic

from core.embeddings import retrieve
from core.prompts import BRIEF_PROMPT, CHAT_SYSTEM_PROMPT, format_chunks
from models.message import ChatResponse

logger = logging.getLogger(__name__)

# Initialize Claude clients once at module level
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
async_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# How many recent turns to include as conversation context
CHAT_HISTORY_TURNS: int = 10


def chat(
    message: str,
    session_id: str,
    research_question: str,
    paper_count: int,
    history: list[dict],
) -> ChatResponse:
    """Generate a grounded chat response using RAG.

    Retrieves relevant chunks for the message, then calls Claude with a
    strict grounding system prompt. Every claim in the response must cite
    a real source chunk.

    Args:
        message: The user's current message.
        session_id: The project session ID for ChromaDB lookup.
        research_question: Project research question for system prompt context.
        paper_count: Number of indexed papers for system prompt context.
        history: Recent chat history as list of {role, content} dicts.

    Returns:
        ChatResponse with response text and sources used.
    """
    chunks = retrieve(message, session_id)

    if not chunks:
        return ChatResponse(
            content=(
                "I don't see anything in your uploaded papers that addresses this. "
                "You may want to search for additional literature on this topic."
            ),
            sources=[],
            chunks_retrieved=0,
        )

    chunks_formatted = format_chunks(chunks)

    system_prompt = CHAT_SYSTEM_PROMPT.format(
        research_question=research_question,
        paper_count=paper_count,
    )

    # Build messages: recent history + current message with chunks
    messages = history[-CHAT_HISTORY_TURNS * 2 :]  # last N turns = 2N messages
    messages.append({
        "role": "user",
        "content": (
            f"{message}\n\n"
            f"Here are the relevant source chunks from your papers:\n\n"
            f"{chunks_formatted}"
        ),
    })

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        system=system_prompt,
        messages=messages,
    )

    return ChatResponse(
        content=response.content[0].text,
        sources=list({c["source"] for c in chunks}),
        chunks_retrieved=len(chunks),
    )


def generate_brief(
    research_question: str,
    session_id: str,
) -> ChatResponse:
    """Generate a full structured research brief using all indexed papers.

    Uses a broader retrieval (n=20) to maximize coverage across all uploaded
    papers. Returns the four-section brief: Synthesis, Debates, Gaps, Outline.

    Args:
        research_question: The researcher's core question, used as the retrieval query.
        session_id: The project session ID for ChromaDB lookup.

    Returns:
        ChatResponse with the four-section brief and sources used.
    """
    chunks = retrieve(research_question, session_id, n_results=20)

    if not chunks:
        return ChatResponse(
            content=(
                "No relevant content found in your uploaded papers. "
                "Make sure your papers are fully indexed before generating a brief."
            ),
            sources=[],
            chunks_retrieved=0,
        )

    chunks_formatted = format_chunks(chunks)

    prompt = BRIEF_PROMPT.format(
        research_question=research_question,
        chunks_formatted=chunks_formatted,
    )

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    return ChatResponse(
        content=response.content[0].text,
        sources=list({c["source"] for c in chunks}),
        chunks_retrieved=len(chunks),
    )


async def stream_chat(
    message: str,
    session_id: str,
    research_question: str,
    paper_count: int,
    history: list[dict],
) -> AsyncIterator[str]:
    """Stream a grounded chat response chunk by chunk via SSE."""
    chunks = await asyncio.to_thread(retrieve, message, session_id)

    if not chunks:
        yield _sse("chunk", text=(
            "I don't see anything in your uploaded papers that addresses this. "
            "You may want to search for additional literature on this topic."
        ))
        yield _sse("done", sources=[], chunks_retrieved=0)
        return

    system_prompt = CHAT_SYSTEM_PROMPT.format(
        research_question=research_question,
        paper_count=paper_count,
    )
    messages = list(history[-CHAT_HISTORY_TURNS * 2:])
    messages.append({
        "role": "user",
        "content": (
            f"{message}\n\n"
            f"Here are the relevant source chunks from your papers:\n\n"
            f"{format_chunks(chunks)}"
        ),
    })
    sources = list({c["source"] for c in chunks})

    try:
        async with async_client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield _sse("chunk", text=text)
    except Exception as exc:
        logger.error("stream_chat error: %s", exc)
        yield _sse("error", message=str(exc))
        return

    yield _sse("done", sources=sources, chunks_retrieved=len(chunks))


async def stream_brief(
    research_question: str,
    session_id: str,
) -> AsyncIterator[str]:
    """Stream a full research brief chunk by chunk via SSE."""
    chunks = await asyncio.to_thread(retrieve, research_question, session_id, 20)

    if not chunks:
        yield _sse("chunk", text=(
            "No relevant content found in your uploaded papers. "
            "Make sure your papers are fully indexed before generating a brief."
        ))
        yield _sse("done", sources=[], chunks_retrieved=0)
        return

    prompt = BRIEF_PROMPT.format(
        research_question=research_question,
        chunks_formatted=format_chunks(chunks),
    )
    sources = list({c["source"] for c in chunks})

    try:
        async with async_client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield _sse("chunk", text=text)
    except Exception as exc:
        logger.error("stream_brief error: %s", exc)
        yield _sse("error", message=str(exc))
        return

    yield _sse("done", sources=sources, chunks_retrieved=len(chunks))


def _sse(event_type: str, **payload) -> str:
    """Format a server-sent event data line."""
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"
