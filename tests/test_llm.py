# tests/test_llm.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm import (
    ANTHROPIC_MODEL,
    OPENAI_MODEL,
    complete,
    detect_provider,
    stream_complete,
)

# ---------------------------------------------------------------------------
# detect_provider
# ---------------------------------------------------------------------------


def test_detect_provider_anthropic():
    assert detect_provider("sk-ant-api03-abc123") == "anthropic"


def test_detect_provider_openai():
    assert detect_provider("sk-proj-abc123") == "openai"


def test_detect_provider_plain_sk():
    assert detect_provider("sk-abc123") == "openai"


def test_detect_provider_invalid_raises():
    with pytest.raises(ValueError, match="Unrecognized API key format"):
        detect_provider("garbage")


def test_detect_provider_empty_raises():
    with pytest.raises(ValueError):
        detect_provider("")


# ---------------------------------------------------------------------------
# complete() — anthropic path
# ---------------------------------------------------------------------------


def test_complete_anthropic_path():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Anthropic answer")]
    mock_client_instance = MagicMock()
    mock_client_instance.messages.create.return_value = mock_response

    with patch("core.llm.anthropic.Anthropic", return_value=mock_client_instance):
        result = complete(
            messages=[{"role": "user", "content": "hello"}],
            system="You are helpful.",
            api_key="sk-ant-test",
            max_tokens=100,
        )

    assert result == "Anthropic answer"
    mock_client_instance.messages.create.assert_called_once_with(
        model=ANTHROPIC_MODEL,
        max_tokens=100,
        system="You are helpful.",
        messages=[{"role": "user", "content": "hello"}],
    )


def test_complete_anthropic_passes_system():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="ok")]
    mock_client_instance = MagicMock()
    mock_client_instance.messages.create.return_value = mock_response

    with patch("core.llm.anthropic.Anthropic", return_value=mock_client_instance):
        complete(
            messages=[],
            system="Custom system prompt",
            api_key="sk-ant-xyz",
        )

    call_kwargs = mock_client_instance.messages.create.call_args[1]
    assert call_kwargs["system"] == "Custom system prompt"


# ---------------------------------------------------------------------------
# complete() — openai path
# ---------------------------------------------------------------------------


def test_complete_openai_path():
    mock_message = MagicMock()
    mock_message.content = "OpenAI answer"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.return_value = mock_response

    with patch("core.llm.openai.OpenAI", return_value=mock_client_instance):
        result = complete(
            messages=[{"role": "user", "content": "hello"}],
            system="You are helpful.",
            api_key="sk-proj-test",
            max_tokens=200,
        )

    assert result == "OpenAI answer"
    call_kwargs = mock_client_instance.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == OPENAI_MODEL
    assert call_kwargs["max_tokens"] == 200
    # System message is prepended to messages
    assert call_kwargs["messages"][0] == {
        "role": "system",
        "content": "You are helpful.",
    }
    assert call_kwargs["messages"][1] == {"role": "user", "content": "hello"}


# ---------------------------------------------------------------------------
# stream_complete() — anthropic path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_complete_anthropic():
    chunks = ["Hello", " world", "!"]

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=False)
    mock_stream.text_stream = _async_iter(chunks)

    mock_async_client = MagicMock()
    mock_async_client.messages.stream.return_value = mock_stream

    with patch("core.llm.anthropic.AsyncAnthropic", return_value=mock_async_client):
        result = []
        async for text in stream_complete(
            messages=[{"role": "user", "content": "hi"}],
            system="sys",
            api_key="sk-ant-test",
        ):
            result.append(text)

    assert result == chunks


# ---------------------------------------------------------------------------
# stream_complete() — openai path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_complete_openai_skips_none_deltas():
    def make_chunk(content):
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = content
        return chunk

    raw_chunks = [
        make_chunk("Hi"),
        make_chunk(None),  # should be skipped
        make_chunk(" there"),
    ]

    mock_async_client = AsyncMock()
    mock_async_client.chat.completions.create = AsyncMock(
        return_value=_async_iter(raw_chunks)
    )

    with patch("core.llm.openai.AsyncOpenAI", return_value=mock_async_client):
        result = []
        async for text in stream_complete(
            messages=[{"role": "user", "content": "hi"}],
            system="sys",
            api_key="sk-openai-test",
        ):
            result.append(text)

    assert result == ["Hi", " there"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _async_iter(items):
    for item in items:
        yield item
