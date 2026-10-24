from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

EMBEDDING_DIMENSIONS = 768


@dataclass(frozen=True)
class EmbeddingDocument:
    title: str | None
    text: str


class EmbeddingClient(Protocol):
    async def embed_documents(
        self, documents: Sequence[EmbeddingDocument]
    ) -> list[list[float]]:
        raise NotImplementedError()

    async def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError()
