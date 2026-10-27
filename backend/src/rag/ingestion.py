from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from llm.embeddings import EmbeddingClient, EmbeddingDocument
from rag.entries import ContentEntry, EmbeddedEntry
from rag.repository import ContentChunkRepository

INGESTION_BATCH_SIZE = 20

Commit = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class IngestionReport:
    embedded: int
    unchanged: int
    removed: int
    batches: int


class ContentIngestionService:
    def __init__(
        self,
        repository: ContentChunkRepository,
        embedder: EmbeddingClient,
        commit: Commit,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._commit = commit

    async def ingest(self, entries: Sequence[ContentEntry]) -> IngestionReport:
        by_hash = {entry.content_hash: entry for entry in entries}
        stored_models = await self._repository.get_embedding_models()
        pending = [
            entry
            for content_hash, entry in by_hash.items()
            if stored_models.get(content_hash) != self._embedder.model
        ]

        batches = [
            pending[start : start + INGESTION_BATCH_SIZE]
            for start in range(0, len(pending), INGESTION_BATCH_SIZE)
        ]
        for batch in batches:
            await self._ingest_batch(batch)
        removed = await self._repository.delete_except(by_hash.keys())
        await self._commit()

        return IngestionReport(
            embedded=len(pending),
            unchanged=len(by_hash) - len(pending),
            removed=removed,
            batches=len(batches),
        )

    async def _ingest_batch(self, batch: Sequence[ContentEntry]) -> None:
        vectors = await self._embedder.embed_documents(
            [EmbeddingDocument(entry.title, entry.content) for entry in batch]
        )
        await self._repository.upsert_many(
            [
                EmbeddedEntry(entry, vector, self._embedder.model)
                for entry, vector in zip(batch, vectors, strict=True)
            ]
        )
        await self._commit()
