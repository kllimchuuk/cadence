import pytest
from pydantic import BaseModel

from llm.exceptions import LLMResponseError
from llm.gemini_client import GeminiClient


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


class _FakeAio:
    def __init__(self, models: _FakeModels) -> None:
        self.models = models


class _FakeGenaiClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.aio = _FakeAio(_FakeModels(response))


@pytest.mark.asyncio
async def test_generate_returns_the_response_text() -> None:
    client = GeminiClient(_FakeGenaiClient(_FakeResponse(text="hello")), "gemini-flash")

    assert await client.generate("prompt") == "hello"


@pytest.mark.asyncio
async def test_generate_raises_when_gemini_returns_no_text() -> None:
    client = GeminiClient(
        _FakeGenaiClient(
            _FakeResponse(text=None, candidates=[_FakeCandidate("SAFETY")])
        ),
        "gemini-flash",
    )

    with pytest.raises(LLMResponseError):
        await client.generate("prompt")


@pytest.mark.asyncio
async def test_generate_raises_when_the_prompt_itself_was_blocked() -> None:
    client = GeminiClient(
        _FakeGenaiClient(_FakeResponse(text=None, block_reason="SAFETY")),
        "gemini-flash",
    )

    with pytest.raises(LLMResponseError, match="SAFETY"):
        await client.generate("prompt")


@pytest.mark.asyncio
async def test_generate_structured_returns_the_parsed_model() -> None:
    parsed = _Schema(value="x")
    client = GeminiClient(
        _FakeGenaiClient(_FakeResponse(parsed=parsed)), "gemini-flash"
    )

    result = await client.generate_structured("prompt", _Schema)

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
    )

    with pytest.raises(LLMResponseError):
        await client.generate_structured("prompt", _Schema)
