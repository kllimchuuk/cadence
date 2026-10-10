import asyncio

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


class _FakeModels:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.received_kwargs: dict[str, object] | None = None

    async def generate_content(self, **kwargs: object) -> _FakeResponse:
        self.received_kwargs = kwargs
        return self._response


class _FailingModels:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def generate_content(self, **_kwargs: object) -> _FakeResponse:
        raise self._error


class _StalledModels:
    async def generate_content(self, **_kwargs: object) -> _FakeResponse:
        await asyncio.sleep(TIMEOUT_SECONDS)
        return _FakeResponse(text="too late")


class _FakeAio:
    def __init__(self, models: object) -> None:
        self.models = models


class _FakeGenaiClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.aio = _FakeAio(_FakeModels(response))


class _FakeGenaiClientWith:
    def __init__(self, models: object) -> None:
        self.aio = _FakeAio(models)


def _api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"status": "SOME_STATUS"}})


@pytest.mark.asyncio
async def test_generate_returns_the_response_text() -> None:
    client = GeminiClient(
        _FakeGenaiClient(_FakeResponse(text="hello")), "gemini-flash", TIMEOUT_SECONDS
    )

    assert await client.generate(SYSTEM_INSTRUCTION, MESSAGES) == "hello"


@pytest.mark.asyncio
async def test_generate_raises_when_gemini_returns_no_text() -> None:
    client = GeminiClient(
        _FakeGenaiClient(
            _FakeResponse(text=None, candidates=[_FakeCandidate("SAFETY")])
        ),
        "gemini-flash",
        TIMEOUT_SECONDS,
    )

    with pytest.raises(LLMResponseError):
        await client.generate(SYSTEM_INSTRUCTION, MESSAGES)


@pytest.mark.asyncio
async def test_generate_raises_when_the_prompt_itself_was_blocked() -> None:
    client = GeminiClient(
        _FakeGenaiClient(_FakeResponse(text=None, block_reason="SAFETY")),
        "gemini-flash",
        TIMEOUT_SECONDS,
    )

    with pytest.raises(LLMResponseError, match="SAFETY"):
        await client.generate(SYSTEM_INSTRUCTION, MESSAGES)


@pytest.mark.asyncio
async def test_generate_structured_returns_the_parsed_model() -> None:
    parsed = _Schema(value="x")
    client = GeminiClient(
        _FakeGenaiClient(_FakeResponse(parsed=parsed)), "gemini-flash", TIMEOUT_SECONDS
    )

    result = await client.generate_structured(SYSTEM_INSTRUCTION, MESSAGES, _Schema)

    assert result is parsed


@pytest.mark.asyncio
async def test_generate_structured_raises_when_gemini_returns_nothing_parseable() -> (
    None
):
    client = GeminiClient(
        _FakeGenaiClient(
            _FakeResponse(parsed=None, candidates=[_FakeCandidate("MAX_TOKENS")])
        ),
        "gemini-flash",
        TIMEOUT_SECONDS,
    )

    with pytest.raises(LLMResponseError):
        await client.generate_structured(SYSTEM_INSTRUCTION, MESSAGES, _Schema)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [429, 500, 503])
async def test_a_rate_limit_or_server_error_is_reported_as_unavailable(
    code: int,
) -> None:
    client = GeminiClient(
        _FakeGenaiClientWith(_FailingModels(_api_error(code))),
        "gemini-flash",
        TIMEOUT_SECONDS,
    )

    with pytest.raises(LLMUnavailableError):
        await client.generate(SYSTEM_INSTRUCTION, MESSAGES)


@pytest.mark.asyncio
async def test_a_client_error_is_not_reported_as_unavailable() -> None:
    client = GeminiClient(
        _FakeGenaiClientWith(_FailingModels(_api_error(400))),
        "gemini-flash",
        TIMEOUT_SECONDS,
    )

    with pytest.raises(errors.APIError):
        await client.generate(SYSTEM_INSTRUCTION, MESSAGES)


@pytest.mark.asyncio
async def test_a_call_that_outlives_the_timeout_is_reported_as_unavailable() -> None:
    client = GeminiClient(
        _FakeGenaiClientWith(_StalledModels()), "gemini-flash", SHORT_TIMEOUT_SECONDS
    )

    with pytest.raises(LLMUnavailableError):
        await client.generate_structured(SYSTEM_INSTRUCTION, MESSAGES, _Schema)


@pytest.mark.asyncio
async def test_messages_keep_their_roles_and_the_system_instruction_is_separate() -> (
    None
):
    genai_client = _FakeGenaiClient(_FakeResponse(text="hello"))
    client = GeminiClient(genai_client, "gemini-flash", TIMEOUT_SECONDS)

    await client.generate(SYSTEM_INSTRUCTION, MESSAGES)

    request = genai_client.aio.models.received_kwargs
    assert [content.role for content in request["contents"]] == [
        "user",
        "model",
        "user",
    ]
    assert [content.parts[0].text for content in request["contents"]] == [
        message.content for message in MESSAGES
    ]
    assert request["config"].system_instruction == SYSTEM_INSTRUCTION
