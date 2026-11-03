import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from llm.embeddings import EmbeddingClient, EmbeddingDocument
from llm.exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)

ResultT = TypeVar("ResultT")


class RetryingEmbeddingClient:
    def __init__(
        self,
        inner: EmbeddingClient,
        max_attempts: int,
        base_delay_seconds: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._inner = inner
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds
        self._sleep = sleep

    @property
    def model(self) -> str:
        return self._inner.model

    async def embed_documents(
        self, documents: Sequence[EmbeddingDocument]
    ) -> list[list[float]]:
        return await self._retry(lambda: self._inner.embed_documents(documents))

    async def embed_query(self, text: str) -> list[float]:
        return await self._retry(lambda: self._inner.embed_query(text))

    async def _retry(self, call: Callable[[], Awaitable[ResultT]]) -> ResultT:
        for attempt in range(1, self._max_attempts):
            try:
                return await call()
            except LLMUnavailableError:
                delay = self._base_delay_seconds * 2 ** (attempt - 1)
                logger.warning(
                    "Embedding provider unavailable; retrying in %.1fs "
                    "(attempt %d of %d)",
                    delay,
                    attempt,
                    self._max_attempts,
                )
                await self._sleep(delay)
        return await call()
