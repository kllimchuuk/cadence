from collections.abc import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from llm.embeddings import EmbeddingDocument
from llm.exceptions import LLMUnavailableError
from rag.entries import ContentEntry
from rag.ingestion import INGESTION_BATCH_SIZE, ContentIngestionService
from rag.models import Corpus
from rag.repository import ContentChunkRepository, ContentChunkRepositoryImpl
from tests.fakes import FakeEmbeddingClient


@pytest.fixture
def repository(session: AsyncSession) -> ContentChunkRepository:
    return ContentChunkRepositoryImpl(session)


@pytest.fixture
def embedder() -> FakeEmbeddingClient:
    return FakeEmbeddingClient()


class CommitCounter:
    def __init__(self) -> None:
        self.count = 0

    async def __call__(self) -> None:
        self.count += 1


class FailingOnSecondCallEmbeddingClient(FakeEmbeddingClient):
    async def embed_documents(
        self, documents: Sequence[EmbeddingDocument]
    ) -> list[list[float]]:
        if self.document_calls:
            raise LLMUnavailableError("503 UNAVAILABLE")
        return await super().embed_documents(documents)


def _service(
    repository: ContentChunkRepository,
    embedder: FakeEmbeddingClient,
    commit: CommitCounter | None = None,
) -> ContentIngestionService:
    return ContentIngestionService(repository, embedder, commit or CommitCounter())


def _grammar(skill_key: str, content: str = "A rule.") -> ContentEntry:
    return ContentEntry(
        corpus=Corpus.GRAMMAR_REFERENCE,
        skill_key=skill_key,
        title=skill_key,
        content=content,
    )


@pytest.mark.asyncio
async def test_new_entries_are_embedded_and_stored(
    repository: ContentChunkRepository, embedder: FakeEmbeddingClient
) -> None:
    entries = [_grammar("articles"), _grammar("modal_verbs")]

    report = await _service(repository, embedder).ingest(entries)

    assert (report.embedded, report.unchanged, report.removed, report.batches) == (
        2,
        0,
        0,
        1,
    )
    assert set(await repository.get_embedding_models()) == {
        entry.content_hash for entry in entries
    }
    assert [document.title for document in embedder.document_calls[0]] == [
        "articles",
        "modal_verbs",
    ]


@pytest.mark.asyncio
async def test_ingesting_the_same_corpus_twice_embeds_nothing_the_second_time(
    repository: ContentChunkRepository, embedder: FakeEmbeddingClient
) -> None:
    entries = [_grammar("articles")]
    service = _service(repository, embedder)
    await service.ingest(entries)

    report = await service.ingest(entries)

    assert (report.embedded, report.unchanged, report.removed) == (0, 1, 0)
    assert report.batches == 0
    assert len(embedder.document_calls) == 1


@pytest.mark.asyncio
async def test_an_edited_entry_is_re_embedded_and_the_old_version_removed(
    repository: ContentChunkRepository, embedder: FakeEmbeddingClient
) -> None:
    service = _service(repository, embedder)
    await service.ingest([_grammar("articles", "Old rule.")])
    edited = _grammar("articles", "New rule.")

    report = await service.ingest([edited])

    assert (report.embedded, report.unchanged, report.removed) == (1, 0, 1)
    assert set(await repository.get_embedding_models()) == {edited.content_hash}


@pytest.mark.asyncio
async def test_entries_built_with_another_model_are_re_embedded(
    repository: ContentChunkRepository, embedder: FakeEmbeddingClient
) -> None:
    entries = [_grammar("articles")]
    await _service(repository, FakeEmbeddingClient("old-model")).ingest(entries)

    report = await _service(repository, FakeEmbeddingClient("new-model")).ingest(
        entries
    )

    assert (report.embedded, report.unchanged, report.removed) == (1, 0, 0)
    assert await repository.get_embedding_models() == {
        entries[0].content_hash: "new-model"
    }


@pytest.mark.asyncio
async def test_identical_entries_in_the_source_are_stored_once(
    repository: ContentChunkRepository, embedder: FakeEmbeddingClient
) -> None:
    report = await _service(repository, embedder).ingest(
        [_grammar("articles"), _grammar("articles")]
    )

    assert report.embedded == 1
    assert len(await repository.get_embedding_models()) == 1


@pytest.mark.asyncio
async def test_entries_are_embedded_and_committed_batch_by_batch(
    repository: ContentChunkRepository, embedder: FakeEmbeddingClient
) -> None:
    entries = [_grammar(f"skill_{index}") for index in range(INGESTION_BATCH_SIZE + 1)]
    commit = CommitCounter()

    report = await _service(repository, embedder, commit).ingest(entries)

    assert report.batches == 2
    assert [len(call) for call in embedder.document_calls] == [
        INGESTION_BATCH_SIZE,
        1,
    ]
    assert commit.count == 3


@pytest.mark.asyncio
async def test_a_failure_keeps_the_committed_batches_and_removes_nothing(
    repository: ContentChunkRepository,
) -> None:
    stale = _grammar("stale")
    await _service(repository, FakeEmbeddingClient()).ingest([stale])
    entries = [_grammar(f"skill_{index}") for index in range(INGESTION_BATCH_SIZE + 1)]
    commit = CommitCounter()

    with pytest.raises(LLMUnavailableError):
        await _service(repository, FailingOnSecondCallEmbeddingClient(), commit).ingest(
            entries
        )

    stored = set(await repository.get_embedding_models())
    assert stale.content_hash in stored
    assert len(stored) == 1 + INGESTION_BATCH_SIZE
    assert commit.count == 1
