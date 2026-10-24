from collections.abc import Collection

from rag.embeddings import EmbeddingClient
from rag.models import ContentChunk, Corpus
from rag.repository import ContentChunkRepository


class ContentRetrievalService:
    def __init__(
        self, repository: ContentChunkRepository, embedder: EmbeddingClient
    ) -> None:
        self._repository = repository
        self._embedder = embedder

    async def search_scenario_content(
        self, scenario_id: str, query: str, limit: int
    ) -> list[ContentChunk]:
        return await self._repository.search(
            Corpus.SCENARIO_CONTENT,
            await self._embedder.embed_query(query),
            limit,
            scenario_id=scenario_id,
        )


class GrammarReferenceService:
    def __init__(self, repository: ContentChunkRepository) -> None:
        self._repository = repository

    async def get_rules(self, skill_keys: Collection[str]) -> list[ContentChunk]:
        return await self._repository.get_grammar_rules(skill_keys)
