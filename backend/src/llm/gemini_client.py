from collections.abc import AsyncIterator, Sequence

from google import genai
from google.genai import types

from llm.client import ChatMessage, MessageRole, SchemaT
from llm.exceptions import LLMResponseError
from llm.gemini_call import call_gemini

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
        chunks = await call_gemini(
            self._client.aio.models.generate_content_stream(
                model=self._model,
                contents=_to_contents(messages),
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ),
            ),
            self._timeout_seconds,
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
        response = await call_gemini(
            self._client.aio.models.generate_content(
                model=self._model,
                contents=_to_contents(messages),
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            ),
            self._timeout_seconds,
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
            return await call_gemini(anext(chunks), self._timeout_seconds)
        except StopAsyncIteration:
            return None
