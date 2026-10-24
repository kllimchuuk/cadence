import asyncio
from collections.abc import Awaitable
from http import HTTPStatus
from typing import TypeVar

from google.genai import errors

from llm.exceptions import LLMUnavailableError

ResultT = TypeVar("ResultT")


def _is_transient(error: errors.APIError) -> bool:
    return (
        error.code == HTTPStatus.TOO_MANY_REQUESTS
        or error.code >= HTTPStatus.INTERNAL_SERVER_ERROR
    )


async def call_gemini(request: Awaitable[ResultT], timeout_seconds: float) -> ResultT:
    try:
        async with asyncio.timeout(timeout_seconds):
            return await request
    except TimeoutError as error:
        raise LLMUnavailableError(f"no response within {timeout_seconds}s") from error
    except errors.APIError as error:
        if _is_transient(error):
            raise LLMUnavailableError(f"{error.code} {error.status}") from error
        raise
