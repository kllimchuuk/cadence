import asyncio

import pytest
from google.genai import errors

from llm.exceptions import LLMResponseError, LLMUnavailableError
from llm.gemini_embedding_client import (
    MAX_DOCUMENTS_PER_REQUEST,
    GeminiEmbeddingClient,
)
from rag.embeddings import EMBEDDING_DIMENSIONS, EmbeddingDocument

TIMEOUT_SECONDS = 1
SHORT_TIMEOUT_SECONDS = 0.01


class _FakeEmbedding:
    def __init__(self, values: list[float]) -> None:
        self.values = values


class _FakeEmbedResponse:
    def __init__(self, embeddings: list[_FakeEmbedding] | None) -> None:
        self.embeddings = embeddings


def _vector(seed: float = 0.1) -> list[float]:
    return [seed] * EMBEDDING_DIMENSIONS


class _FakeModels:
    def __init__(self, embeddings: list[_FakeEmbedding] | None = None) -> None:
        self._embeddings = embeddings
        self.requests: list[dict[str, object]] = []

    async def embed_content(self, **kwargs: object) -> _FakeEmbedResponse:
        self.requests.append(kwargs)
        if self._embeddings is not None:
            return _FakeEmbedResponse(self._embeddings)
        return _FakeEmbedResponse(
            [_FakeEmbedding(_vector()) for _ in kwargs["contents"]]
        )


class _FailingModels:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def embed_content(self, **_kwargs: object) -> _FakeEmbedResponse:
        raise self._error


class _NoEmbeddingsModels:
    async def embed_content(self, **_kwargs: object) -> _FakeEmbedResponse:
        return _FakeEmbedResponse(None)


class _StalledModels:
    async def embed_content(self, **_kwargs: object) -> _FakeEmbedResponse:
        await asyncio.sleep(TIMEOUT_SECONDS)
        return _FakeEmbedResponse([])


class _FakeAio:
    def __init__(self, models: object) -> None:
        self.models = models


class _FakeGenaiClient:
    def __init__(self, models: object) -> None:
        self.aio = _FakeAio(models)


def _client(
    models: object, timeout_seconds: float = TIMEOUT_SECONDS
) -> GeminiEmbeddingClient:
    return GeminiEmbeddingClient(
        _FakeGenaiClient(models), "gemini-embedding", timeout_seconds
    )


def _texts(request: dict[str, object]) -> list[str]:
    return [content.parts[0].text for content in request["contents"]]


@pytest.mark.asyncio
async def test_each_document_is_sent_as_its_own_content_with_the_document_prefix() -> (
    None
):
    models = _FakeModels()

    vectors = await _client(models).embed_documents(
        [EmbeddingDocument("Past simple", "Use -ed."), EmbeddingDocument(None, "Hi.")]
    )

    assert len(vectors) == 2
    assert _texts(models.requests[0]) == [
        "title: Past simple | text: Use -ed.",
        "title: none | text: Hi.",
    ]


@pytest.mark.asyncio
async def test_a_query_gets_the_query_prefix_and_returns_one_vector() -> None:
    models = _FakeModels()

    vector = await _client(models).embed_query("tell me about yourself")

    assert vector == _vector()
    assert _texts(models.requests[0]) == [
        "task: search result | query: tell me about yourself"
    ]


@pytest.mark.asyncio
async def test_the_vector_is_truncated_to_the_column_dimension_without_a_task_type() -> (
    None
):
    models = _FakeModels()

    await _client(models).embed_query("hello")

    config = models.requests[0]["config"]
    assert config.output_dimensionality == EMBEDDING_DIMENSIONS
    assert config.task_type is None
    assert models.requests[0]["model"] == "gemini-embedding"


@pytest.mark.asyncio
async def test_documents_are_split_into_requests_of_the_api_limit() -> None:
    models = _FakeModels()
    documents = [
        EmbeddingDocument(None, f"text {number}")
        for number in range(MAX_DOCUMENTS_PER_REQUEST + 1)
    ]

    vectors = await _client(models).embed_documents(documents)

    assert len(vectors) == len(documents)
    assert [len(request["contents"]) for request in models.requests] == [
        MAX_DOCUMENTS_PER_REQUEST,
        1,
    ]


@pytest.mark.asyncio
async def test_no_documents_make_no_request() -> None:
    models = _FakeModels()

    assert await _client(models).embed_documents([]) == []
    assert models.requests == []


@pytest.mark.asyncio
async def test_fewer_embeddings_than_documents_is_a_response_error() -> None:
    client = _client(_FakeModels(embeddings=[_FakeEmbedding(_vector())]))

    with pytest.raises(LLMResponseError, match="expected 2"):
        await client.embed_documents(
            [EmbeddingDocument(None, "a"), EmbeddingDocument(None, "b")]
        )


@pytest.mark.asyncio
async def test_a_vector_of_the_wrong_dimension_is_a_response_error() -> None:
    client = _client(_FakeModels(embeddings=[_FakeEmbedding([0.1, 0.2])]))

    with pytest.raises(LLMResponseError, match="768"):
        await client.embed_query("hello")


@pytest.mark.asyncio
async def test_a_missing_embeddings_list_is_a_response_error() -> None:
    with pytest.raises(LLMResponseError):
        await _client(_NoEmbeddingsModels()).embed_query("hello")


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [429, 500, 503])
async def test_a_rate_limit_or_server_error_is_reported_as_unavailable(
    code: int,
) -> None:
    error = errors.APIError(code, {"error": {"status": "SOME_STATUS"}})

    with pytest.raises(LLMUnavailableError):
        await _client(_FailingModels(error)).embed_query("hello")


@pytest.mark.asyncio
async def test_a_client_error_is_not_reported_as_unavailable() -> None:
    error = errors.APIError(400, {"error": {"status": "INVALID_ARGUMENT"}})

    with pytest.raises(errors.APIError):
        await _client(_FailingModels(error)).embed_query("hello")


@pytest.mark.asyncio
async def test_a_call_that_outlives_the_timeout_is_unavailable() -> None:
    client = _client(_StalledModels(), SHORT_TIMEOUT_SECONDS)

    with pytest.raises(LLMUnavailableError):
        await client.embed_query("hello")
