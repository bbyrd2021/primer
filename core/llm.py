# core/llm.py
"""
Provider-agnostic LLM adapter for Primer.

Supports Anthropic (sk-ant-...) and OpenAI (sk-...) keys.
Both providers expose the same interface to the rest of the codebase:
  - complete(messages, system, api_key, max_tokens) -> str
  - stream_complete(messages, system, api_key, max_tokens) -> AsyncIterator[str]

Key detection is based on key prefix:
  - "sk-ant-" → Anthropic (claude-sonnet-4-5)
  - "sk-"     → OpenAI    (gpt-4o)
"""

from __future__ import annotations

from typing import AsyncIterator

import anthropic
import openai

# Default models per provider — change here to upgrade globally
ANTHROPIC_MODEL = "claude-sonnet-4-5"
OPENAI_MODEL = "gpt-4o"

MAX_TOKENS = 2000
BRIEF_MAX_TOKENS = 4000


def detect_provider(api_key: str) -> str:
    """Return 'anthropic' or 'openai' based on key prefix."""
    if api_key.startswith("sk-ant-"):
        return "anthropic"
    elif api_key.startswith("sk-"):
        return "openai"
    else:
        raise ValueError("Unrecognized API key format. Expected sk-ant-... or sk-...")


def complete(
    messages: list[dict],
    system: str,
    api_key: str,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """
    Synchronous completion. Returns the response text as a string.

    Args:
        messages: List of {role, content} dicts. Do NOT include system message here.
        system: System prompt string.
        api_key: User-supplied API key.
        max_tokens: Max tokens for the response.

    Returns:
        Response text as a plain string.
    """
    provider = detect_provider(api_key)

    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    else:  # openai
        client = openai.OpenAI(api_key=api_key)
        full_messages = [{"role": "system", "content": system}] + messages
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=max_tokens,
            messages=full_messages,
        )
        return response.choices[0].message.content


async def stream_complete(
    messages: list[dict],
    system: str,
    api_key: str,
    max_tokens: int = MAX_TOKENS,
) -> AsyncIterator[str]:
    """
    Async streaming completion. Yields text chunks as they arrive.

    Args:
        messages: List of {role, content} dicts. Do NOT include system message here.
        system: System prompt string.
        api_key: User-supplied API key.
        max_tokens: Max tokens for the response.

    Yields:
        String chunks of the response as they stream.
    """
    provider = detect_provider(api_key)

    if provider == "anthropic":
        async_client = anthropic.AsyncAnthropic(api_key=api_key)
        async with async_client.messages.stream(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    else:  # openai
        async_client = openai.AsyncOpenAI(api_key=api_key)
        full_messages = [{"role": "system", "content": system}] + messages
        stream = await async_client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=max_tokens,
            messages=full_messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta is not None:
                yield delta
