import asyncio
from collections.abc import Sequence
from http import HTTPStatus

from google import genai
from google.genai import errors, types

from llm.client import ChatMessage, MessageRole, SchemaT
from llm.exceptions import LLMResponseError, LLMUnavailableError

_GEMINI_ROLES = {MessageRole.USER: "user", MessageRole.ASSISTANT: "model"}


def _to_contents(messages: Sequence[ChatMessage]) -> list[types.Content]:
    return [
        types.Content(
            role=_GEMINI_ROLES[message.role], parts=[types.Part(text=message.content)]
        )
        for message in messages
    ]


def _diagnose(response: types.GenerateContentResponse) -> str:
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

    async def generate(
        self, system_instruction: str, messages: Sequence[ChatMessage]
    ) -> str:
        response = await self._generate_content(
            contents=_to_contents(messages),
            config=types.GenerateContentConfig(system_instruction=system_instruction),
        )
        if response.text is None:
            raise LLMResponseError(f"no text ({_diagnose(response)})")
        return response.text

    async def generate_structured(
        self,
        system_instruction: str,
        messages: Sequence[ChatMessage],
        schema: type[SchemaT],
    ) -> SchemaT:
        response = await self._generate_content(
            contents=_to_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        if response.parsed is None:
            raise LLMResponseError(
                f"no parseable {schema.__name__} ({_diagnose(response)})"
            )
        return response.parsed

    async def _generate_content(
        self, **request: object
    ) -> types.GenerateContentResponse:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._client.aio.models.generate_content(
                    model=self._model, **request
                )
        except TimeoutError as error:
            raise LLMUnavailableError(
                f"no response within {self._timeout_seconds}s"
            ) from error
        except errors.APIError as error:
            if _is_transient(error):
                raise LLMUnavailableError(f"{error.code} {error.status}") from error
            raise
