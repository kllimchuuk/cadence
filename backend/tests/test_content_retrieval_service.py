import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rag.repository import ContentChunkRepositoryImpl
from rag.service import ContentRetrievalService

from tests.fakes import FakeEmbeddingClient


@pytest.mark.asyncio
async def test_a_blank_grammar_query_returns_nothing_without_embedding(
    session: AsyncSession,
) -> None:
    embedder = FakeEmbeddingClient()
    service = ContentRetrievalService(ContentChunkRepositoryImpl(session), embedder)

    assert await service.search_grammar_reference("  \n", limit=6) == []
    assert embedder.queries == []
