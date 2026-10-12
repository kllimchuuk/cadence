import asyncio
from collections.abc import AsyncIterator

import pytest
from google.genai import errors
from pydantic import BaseModel

from llm.client import ChatMessage, MessageRole
from llm.exceptions import LLMResponseError, LLMUnavailableError
from llm.gemini_client import GeminiClient

TIMEOUT_SECONDS = 1
SHORT_TIMEOUT_SECONDS = 0.01
SYSTEM_INSTRUCTION = "You are Priya, a hiring manager."
MESSAGES = (
    ChatMessage(MessageRole.USER, "Hello."),
    ChatMessage(MessageRole.ASSISTANT, "Hi, thanks for joining."),
    ChatMessage(MessageRole.USER, "Glad to be here."),
)


class _Schema(BaseModel):
    value: str


class _FakeCandidate:
    def __init__(self, finish_reason: str) -> None:
        self.finish_reason = finish_reason


class _FakePromptFeedback:
    def __init__(self, block_reason: str | None) -> None:
        self.block_reason = block_reason


class _FakeResponse:
    def __init__(
        self,
        text: str | None = None,
        parsed: object | None = None,
        candidates: list[_FakeCandidate] | None = None,
        block_reason: str | None = None,
    ) -> None:
        self.text = text
        self.parsed = parsed
        self.candidates = candidates or []
        self.prompt_feedback = (
            _FakePromptFeedback(block_reason) if block_reason else None
        )


async def _chunks(responses: list[_FakeResponse]) -> AsyncIterator[_FakeResponse]:
    for response in responses:
        yield response


async def _stalling_chunks(first: _FakeResponse) -> AsyncIterator[_FakeResponse]:
    yield first
    await asyncio.sleep(TIMEOUT_SECONDS)
    yield _FakeResponse(text="too late")


class _FakeModels:
    def __init__(
        self,
        response: _FakeResponse | None = None,
        chunks: list[_FakeResponse] | None = None,
    ) -> None:
        self._response = response
        self._chunks = chunks or []
        self.received_kwargs: dict[str, object] | None = None

    async def generate_content(self, **kwargs: object) -> _FakeResponse:
        self.received_kwargs = kwargs
        return self._response

    async def generate_content_stream(
        self, **kwargs: object
    ) -> AsyncIterator[_FakeResponse]:
        self.received_kwargs = kwargs
        return _chunks(self._chunks)


class _FailingModels:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def generate_content(self, **_kwargs: object) -> _FakeResponse:
        raise self._error

    async def generate_content_stream(
        self, **_kwargs: object
    ) -> AsyncIterator[_FakeResponse]:
        raise self._error


class _StalledModels:
    async def generate_content(self, **_kwargs: object) -> _FakeResponse:
        await asyncio.sleep(TIMEOUT_SECONDS)
        return _FakeResponse(text="too late")

    async def generate_content_stream(
        self, **_kwargs: object
    ) -> AsyncIterator[_FakeResponse]:
        return _stalling_chunks(_FakeResponse(text="Hello"))


class _FakeAio:
    def __init__(self, models: object) -> None:
        self.models = models


class _FakeGenaiClient:
    def __init__(self, models: object) -> None:
        self.aio = _FakeAio(models)


def _client(models: object, timeout_seconds: float = TIMEOUT_SECONDS) -> GeminiClient:
    return GeminiClient(_FakeGenaiClient(models), "gemini-flash", timeout_seconds)


def _api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"status": "SOME_STATUS"}})


async def _collect(client: GeminiClient) -> list[str]:
    return [delta async for delta in client.stream(SYSTEM_INSTRUCTION, MESSAGES)]


@pytest.mark.asyncio
async def test_stream_yields_the_text_of_each_chunk() -> None:
    client = _client(
        _FakeModels(chunks=[_FakeResponse(text="Hel"), _FakeResponse(text="lo")])
    )

    assert await _collect(client) == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_stream_skips_chunks_without_text() -> None:
    client = _client(
        _FakeModels(
            chunks=[
                _FakeResponse(text="Hello"),
                _FakeResponse(text=None, candidates=[_FakeCandidate("STOP")]),
            ]
        )
    )

    assert await _collect(client) == ["Hello"]


@pytest.mark.asyncio
async def test_stream_raises_when_gemini_returns_no_text() -> None:
    client = _client(
        _FakeModels(
            chunks=[_FakeResponse(text=None, candidates=[_FakeCandidate("SAFETY")])]
        )
    )

    with pytest.raises(LLMResponseError, match="SAFETY"):
        await _collect(client)


@pytest.mark.asyncio
async def test_stream_raises_when_the_prompt_itself_was_blocked() -> None:
    client = _client(
        _FakeModels(chunks=[_FakeResponse(text=None, block_reason="SAFETY")])
    )

    with pytest.raises(LLMResponseError, match="prompt blocked"):
        await _collect(client)


@pytest.mark.asyncio
async def test_stream_raises_when_the_stream_is_empty() -> None:
    client = _client(_FakeModels(chunks=[]))

    with pytest.raises(LLMResponseError, match="empty stream"):
        await _collect(client)


@pytest.mark.asyncio
async def test_generate_structured_returns_the_parsed_model() -> None:
    parsed = _Schema(value="x")
    client = _client(_FakeModels(response=_FakeResponse(parsed=parsed)))

    result = await client.generate_structured(SYSTEM_INSTRUCTION, MESSAGES, _Schema)

    assert result is parsed


@pytest.mark.asyncio
async def test_generate_structured_raises_when_gemini_returns_nothing_parseable() -> (
    None
):
    client = _client(
        _FakeModels(
            response=_FakeResponse(
                parsed=None, candidates=[_FakeCandidate("MAX_TOKENS")]
            )
        )
    )

    with pytest.raises(LLMResponseError):
        await client.generate_structured(SYSTEM_INSTRUCTION, MESSAGES, _Schema)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [429, 500, 503])
async def test_a_rate_limit_or_server_error_is_reported_as_unavailable(
    code: int,
) -> None:
    client = _client(_FailingModels(_api_error(code)))

    with pytest.raises(LLMUnavailableError):
        await _collect(client)


@pytest.mark.asyncio
async def test_a_client_error_is_not_reported_as_unavailable() -> None:
    client = _client(_FailingModels(_api_error(400)))

    with pytest.raises(errors.APIError):
        await _collect(client)


@pytest.mark.asyncio
async def test_a_structured_call_that_outlives_the_timeout_is_unavailable() -> None:
    client = _client(_StalledModels(), SHORT_TIMEOUT_SECONDS)

    with pytest.raises(LLMUnavailableError):
        await client.generate_structured(SYSTEM_INSTRUCTION, MESSAGES, _Schema)


@pytest.mark.asyncio
async def test_a_stream_that_stalls_between_chunks_is_unavailable() -> None:
    client = _client(_StalledModels(), SHORT_TIMEOUT_SECONDS)
    received = []

    with pytest.raises(LLMUnavailableError):
        async for delta in client.stream(SYSTEM_INSTRUCTION, MESSAGES):
            received.append(delta)

    assert received == ["Hello"]


@pytest.mark.asyncio
async def test_messages_keep_their_roles_and_the_system_instruction_is_separate() -> (
    None
):
    models = _FakeModels(chunks=[_FakeResponse(text="hello")])

    await _collect(_client(models))

    request = models.received_kwargs
    assert [content.role for content in request["contents"]] == [
        "user",
        "model",
        "user",
    ]
    assert [content.parts[0].text for content in request["contents"]] == [
        message.content for message in MESSAGES
    ]
    assert request["config"].system_instruction == SYSTEM_INSTRUCTION
