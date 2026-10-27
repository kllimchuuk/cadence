import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rag.entries import ContentEntry
from rag.ingestion import ContentIngestionService
from rag.models import Corpus
from rag.repository import ContentChunkRepository, ContentChunkRepositoryImpl
from tests.fakes import FakeEmbeddingClient


@pytest.fixture
def repository(session: AsyncSession) -> ContentChunkRepository:
    return ContentChunkRepositoryImpl(session)


@pytest.fixture
def embedder() -> FakeEmbeddingClient:
    return FakeEmbeddingClient()


def _service(
    repository: ContentChunkRepository, embedder: FakeEmbeddingClient
) -> ContentIngestionService:
    return ContentIngestionService(repository, embedder)


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

    assert (report.embedded, report.unchanged, report.removed) == (2, 0, 0)
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
    assert len(embedder.document_calls) == 2
    assert embedder.document_calls[1] == ()


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
