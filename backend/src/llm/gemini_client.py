import asyncio
from collections.abc import AsyncIterator, Awaitable, Sequence
from http import HTTPStatus
from typing import TypeVar

from google import genai
from google.genai import errors, types

from llm.client import ChatMessage, MessageRole, SchemaT
from llm.exceptions import LLMResponseError, LLMUnavailableError

ResultT = TypeVar("ResultT")

_GEMINI_ROLES = {MessageRole.USER: "user", MessageRole.ASSISTANT: "model"}


def _to_contents(messages: Sequence[ChatMessage]) -> list[types.Content]:
    return [
        types.Content(
            role=_GEMINI_ROLES[message.role], parts=[types.Part(text=message.content)]
        )
        for message in messages
    ]


def _diagnose(response: types.GenerateContentResponse | None) -> str:
    if response is None:
        return "empty stream"
    feedback = response.prompt_feedback
    if feedback is not None and feedback.block_reason:
        return f"prompt blocked: {feedback.block_reason}"
    if response.candidates:
        return f"finish_reason={response.candidates[0].finish_reason}"
    return "no candidates returned"


def _is_transient(error: errors.APIError) -> bool:
    return (
        error.code == HTTPStatus.TOO_MANY_REQUESTS
        or error.code >= HTTPStatus.INTERNAL_SERVER_ERROR
    )


class GeminiClient:
    def __init__(
        self, client: genai.Client, model: str, timeout_seconds: float
    ) -> None:
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def stream(
        self, system_instruction: str, messages: Sequence[ChatMessage]
    ) -> AsyncIterator[str]:
        chunks = await self._call(
            self._client.aio.models.generate_content_stream(
                model=self._model,
                contents=_to_contents(messages),
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ),
            )
        )
        last_chunk = None
        produced_text = False
        while (chunk := await self._next_chunk(chunks)) is not None:
            last_chunk = chunk
            if chunk.text:
                produced_text = True
                yield chunk.text
        if not produced_text:
            raise LLMResponseError(f"no text ({_diagnose(last_chunk)})")

    async def generate_structured(
        self,
        system_instruction: str,
        messages: Sequence[ChatMessage],
        schema: type[SchemaT],
    ) -> SchemaT:
        response = await self._call(
            self._client.aio.models.generate_content(
                model=self._model,
                contents=_to_contents(messages),
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        )
        if response.parsed is None:
            raise LLMResponseError(
                f"no parseable {schema.__name__} ({_diagnose(response)})"
            )
        return response.parsed

    async def _next_chunk(
        self, chunks: AsyncIterator[types.GenerateContentResponse]
    ) -> types.GenerateContentResponse | None:
        try:
            return await self._call(anext(chunks))
        except StopAsyncIteration:
            return None

    async def _call(self, request: Awaitable[ResultT]) -> ResultT:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await request
        except TimeoutError as error:
            raise LLMUnavailableError(
                f"no response within {self._timeout_seconds}s"
            ) from error
        except errors.APIError as error:
            if _is_transient(error):
                raise LLMUnavailableError(f"{error.code} {error.status}") from error
            raise
