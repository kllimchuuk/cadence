from abc import ABC, abstractmethod
from collections.abc import Collection, Sequence

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rag.entries import EmbeddedEntry
from rag.models import ContentChunk, Corpus


class ContentChunkRepository(ABC):
    @abstractmethod
    async def get_embedding_models(self) -> dict[str, str]:
        raise NotImplementedError()

    @abstractmethod
    async def upsert_many(self, embedded: Sequence[EmbeddedEntry]) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def delete_except(self, content_hashes: Collection[str]) -> int:
        raise NotImplementedError()

    @abstractmethod
    async def search(
        self,
        corpus: Corpus,
        query_embedding: list[float],
        limit: int,
        scenario_id: str | None = None,
    ) -> list[ContentChunk]:
        raise NotImplementedError()


class ContentChunkRepositoryImpl(ContentChunkRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_embedding_models(self) -> dict[str, str]:
        result = await self._session.execute(
            select(ContentChunk.content_hash, ContentChunk.embedding_model)
        )
        return {content_hash: model for content_hash, model in result.all()}

    async def upsert_many(self, embedded: Sequence[EmbeddedEntry]) -> None:
        if not embedded:
            return
        statement = insert(ContentChunk).values(
            [
                {
                    "corpus": item.entry.corpus,
                    "scenario_id": item.entry.scenario_id,
                    "skill_key": item.entry.skill_key,
                    "title": item.entry.title,
                    "content": item.entry.content,
                    "content_hash": item.entry.content_hash,
                    "embedding_model": item.embedding_model,
                    "embedding": item.embedding,
                }
                for item in embedded
            ]
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[ContentChunk.content_hash],
                set_={
                    "embedding": statement.excluded.embedding,
                    "embedding_model": statement.excluded.embedding_model,
                    "updated_at": func.now(),
                },
            )
        )

    async def delete_except(self, content_hashes: Collection[str]) -> int:
        result = await self._session.execute(
            delete(ContentChunk).where(ContentChunk.content_hash.not_in(content_hashes))
        )
        return result.rowcount

    async def search(
        self,
        corpus: Corpus,
        query_embedding: list[float],
        limit: int,
        scenario_id: str | None = None,
    ) -> list[ContentChunk]:
        await self._session.execute(
            text("SET LOCAL hnsw.iterative_scan = strict_order")
        )
        query = select(ContentChunk).where(ContentChunk.corpus == corpus)
        if scenario_id is not None:
            query = query.where(ContentChunk.scenario_id == scenario_id)
        result = await self._session.execute(
            query.order_by(
                ContentChunk.embedding.cosine_distance(query_embedding)
            ).limit(limit)
        )
        return list(result.scalars())
