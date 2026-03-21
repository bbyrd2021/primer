# core/synthesize.py
import asyncio
import json
import logging
from collections.abc import AsyncIterator

from core.embeddings import retrieve
from core.llm import BRIEF_MAX_TOKENS, complete, stream_complete
from core.prompts import BRIEF_PROMPT, CHAT_SYSTEM_PROMPT, format_chunks
from models.message import ChatResponse

logger = logging.getLogger(__name__)

# How many recent turns to include as conversation context
CHAT_HISTORY_TURNS: int = 10


def chat(
    message: str,
    session_id: str,
    research_question: str,
    paper_count: int,
    history: list[dict[str, str]],
    api_key: str = "",
) -> ChatResponse:
    """Generate a grounded chat response using RAG.

    Retrieves relevant chunks for the message, then calls the LLM with a
    strict grounding system prompt. Every claim in the response must cite
    a real source chunk.

    Args:
        message: The user's current message.
        session_id: The project session ID for ChromaDB lookup.
        research_question: Project research question for system prompt context.
        paper_count: Number of indexed papers for system prompt context.
        history: Recent chat history as list of {role, content} dicts.
        api_key: User-supplied API key.

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
    messages.append(
        {
            "role": "user",
            "content": (
                f"{message}\n\n"
                f"Here are the relevant source chunks from your papers:\n\n"
                f"{chunks_formatted}"
            ),
        }
    )

    text = complete(
        messages=messages,
        system=system_prompt,
        api_key=api_key,
    )

    return ChatResponse(
        content=text,
        sources=list({c["source"] for c in chunks}),
        chunks_retrieved=len(chunks),
    )


def generate_brief(
    research_question: str,
    session_id: str,
    api_key: str = "",
) -> ChatResponse:
    """Generate a full structured research brief using all indexed papers.

    Uses a broader retrieval (n=20) to maximize coverage across all uploaded
    papers. Returns the four-section brief: Synthesis, Debates, Gaps, Outline.

    Args:
        research_question: The researcher's core question, used as the retrieval query.
        session_id: The project session ID for ChromaDB lookup.
        api_key: User-supplied API key.

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

    text = complete(
        messages=[{"role": "user", "content": prompt}],
        system=CHAT_SYSTEM_PROMPT.format(
            research_question=research_question,
            paper_count=len({c["source"] for c in chunks}),
        ),
        api_key=api_key,
        max_tokens=BRIEF_MAX_TOKENS,
    )

    return ChatResponse(
        content=text,
        sources=list({c["source"] for c in chunks}),
        chunks_retrieved=len(chunks),
    )


async def stream_chat(
    message: str,
    session_id: str,
    research_question: str,
    paper_count: int,
    history: list[dict[str, str]],
    api_key: str = "",
) -> AsyncIterator[str]:
    """Stream a grounded chat response chunk by chunk via SSE."""
    chunks = await asyncio.to_thread(retrieve, message, session_id)

    if not chunks:
        yield _sse(
            "chunk",
            text=(
                "I don't see anything in your uploaded papers that addresses this. "
                "You may want to search for additional literature on this topic."
            ),
        )
        yield _sse("done", sources=[], chunks_retrieved=0)
        return

    system_prompt = CHAT_SYSTEM_PROMPT.format(
        research_question=research_question,
        paper_count=paper_count,
    )
    messages = list(history[-CHAT_HISTORY_TURNS * 2 :])
    messages.append(
        {
            "role": "user",
            "content": (
                f"{message}\n\n"
                f"Here are the relevant source chunks from your papers:\n\n"
                f"{format_chunks(chunks)}"
            ),
        }
    )
    sources = list({c["source"] for c in chunks})

    try:
        async for text in stream_complete(
            messages=messages,
            system=system_prompt,
            api_key=api_key,
        ):
            yield _sse("chunk", text=text)
    except Exception as exc:
        logger.error("stream_chat error: %s", exc)
        yield _sse("error", message=str(exc))
        return

    yield _sse("done", sources=sources, chunks_retrieved=len(chunks))


async def stream_brief(
    research_question: str,
    session_id: str,
    api_key: str = "",
) -> AsyncIterator[str]:
    """Stream a full research brief chunk by chunk via SSE."""
    chunks = await asyncio.to_thread(retrieve, research_question, session_id, 20)

    if not chunks:
        yield _sse(
            "chunk",
            text=(
                "No relevant content found in your uploaded papers. "
                "Make sure your papers are fully indexed before generating a brief."
            ),
        )
        yield _sse("done", sources=[], chunks_retrieved=0)
        return

    prompt = BRIEF_PROMPT.format(
        research_question=research_question,
        chunks_formatted=format_chunks(chunks),
    )
    sources = list({c["source"] for c in chunks})

    try:
        async for text in stream_complete(
            messages=[{"role": "user", "content": prompt}],
            system=CHAT_SYSTEM_PROMPT.format(
                research_question=research_question,
                paper_count=len({c["source"] for c in chunks}),
            ),
            api_key=api_key,
            max_tokens=BRIEF_MAX_TOKENS,
        ):
            yield _sse("chunk", text=text)
    except Exception as exc:
        logger.error("stream_brief error: %s", exc)
        yield _sse("error", message=str(exc))
        return

    yield _sse("done", sources=sources, chunks_retrieved=len(chunks))


def _sse(event_type: str, **payload: object) -> str:
    """Format a server-sent event data line."""
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"
