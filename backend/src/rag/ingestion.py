from collections.abc import Sequence
from dataclasses import dataclass

from rag.embeddings import EmbeddingClient, EmbeddingDocument
from rag.entries import ContentEntry, EmbeddedEntry
from rag.repository import ContentChunkRepository


@dataclass(frozen=True)
class IngestionReport:
    embedded: int
    unchanged: int
    removed: int


class ContentIngestionService:
    def __init__(
        self,
        repository: ContentChunkRepository,
        embedder: EmbeddingClient,
    ) -> None:
        self._repository = repository
        self._embedder = embedder

    async def ingest(self, entries: Sequence[ContentEntry]) -> IngestionReport:
        by_hash = {entry.content_hash: entry for entry in entries}
        stored_models = await self._repository.get_embedding_models()
        pending = [
            entry
            for content_hash, entry in by_hash.items()
            if stored_models.get(content_hash) != self._embedder.model
        ]

        vectors = await self._embedder.embed_documents(
            [EmbeddingDocument(entry.title, entry.content) for entry in pending]
        )
        await self._repository.upsert_many(
            [
                EmbeddedEntry(entry, vector, self._embedder.model)
                for entry, vector in zip(pending, vectors, strict=True)
            ]
        )
        removed = await self._repository.delete_except(by_hash.keys())

        return IngestionReport(
            embedded=len(pending),
            unchanged=len(by_hash) - len(pending),
            removed=removed,
        )
