from collections.abc import Sequence

import pytest

from llm.embeddings import EmbeddingDocument
from llm.exceptions import LLMResponseError, LLMUnavailableError
from llm.retrying_embedding_client import RetryingEmbeddingClient
from tests.fakes import FakeEmbeddingClient


class FlakyEmbeddingClient(FakeEmbeddingClient):
    def __init__(self, failures: int, error: Exception) -> None:
        super().__init__()
        self._failures = failures
        self._error = error
        self.attempts = 0

    async def embed_documents(
        self, documents: Sequence[EmbeddingDocument]
    ) -> list[list[float]]:
        self.attempts += 1
        if self.attempts <= self._failures:
            raise self._error
        return await super().embed_documents(documents)


class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _unavailable() -> LLMUnavailableError:
    return LLMUnavailableError("429 RESOURCE_EXHAUSTED")


@pytest.mark.asyncio
async def test_a_transient_failure_is_retried_with_a_doubling_delay() -> None:
    inner = FlakyEmbeddingClient(2, _unavailable())
    sleep = RecordingSleep()
    client = RetryingEmbeddingClient(inner, 5, 2.0, sleep)

    vectors = await client.embed_documents([EmbeddingDocument("A", "b")])

    assert len(vectors) == 1
    assert inner.attempts == 3
    assert sleep.delays == [2.0, 4.0]


@pytest.mark.asyncio
async def test_the_last_failure_is_raised_once_attempts_run_out() -> None:
    inner = FlakyEmbeddingClient(10, _unavailable())
    sleep = RecordingSleep()
    client = RetryingEmbeddingClient(inner, 3, 1.0, sleep)

    with pytest.raises(LLMUnavailableError):
        await client.embed_documents([EmbeddingDocument("A", "b")])

    assert inner.attempts == 3
    assert sleep.delays == [1.0, 2.0]


@pytest.mark.asyncio
async def test_a_non_transient_failure_is_not_retried() -> None:
    inner = FlakyEmbeddingClient(1, LLMResponseError("empty"))
    sleep = RecordingSleep()
    client = RetryingEmbeddingClient(inner, 5, 1.0, sleep)

    with pytest.raises(LLMResponseError):
        await client.embed_documents([EmbeddingDocument("A", "b")])

    assert inner.attempts == 1
    assert sleep.delays == []
