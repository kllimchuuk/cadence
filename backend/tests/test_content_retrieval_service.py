import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rag.entries import ContentEntry, EmbeddedEntry
from rag.models import Corpus
from rag.repository import ContentChunkRepositoryImpl
from rag.service import (
    ContentCorpusService,
    ContentRetrievalService,
    GrammarReferenceService,
)

from tests.fakes import FakeEmbeddingClient, fake_embedding


async def _store_rule(session: AsyncSession, skill_key: str) -> None:
    entry = ContentEntry(
        corpus=Corpus.GRAMMAR_REFERENCE,
        skill_key=skill_key,
        title=skill_key,
        content=f"rule for {skill_key}",
    )
    await ContentChunkRepositoryImpl(session).upsert_many(
        [EmbeddedEntry(entry, fake_embedding(entry.content), "embedding-model")]
    )


@pytest.mark.asyncio
async def test_get_rules_returns_the_requested_rules_ordered_by_skill_key(
    session: AsyncSession,
) -> None:
    for skill_key in ("modal_verbs", "articles", "conditionals"):
        await _store_rule(session, skill_key)
    service = GrammarReferenceService(ContentChunkRepositoryImpl(session))

    rules = await service.get_rules({"modal_verbs", "articles"})

    assert [rule.skill_key for rule in rules] == ["articles", "modal_verbs"]


@pytest.mark.asyncio
async def test_get_rules_with_no_keys_returns_nothing(session: AsyncSession) -> None:
    await _store_rule(session, "articles")
    service = GrammarReferenceService(ContentChunkRepositoryImpl(session))

    assert await service.get_rules(set()) == []


@pytest.mark.asyncio
async def test_scenario_search_only_finds_entries_of_the_embedders_model(
    session: AsyncSession,
) -> None:
    repository = ContentChunkRepositoryImpl(session)
    entry = ContentEntry(
        corpus=Corpus.SCENARIO_CONTENT,
        scenario_id="job_interview",
        title="Experience",
        content="ask about experience",
    )
    await repository.upsert_many(
        [EmbeddedEntry(entry, fake_embedding(entry.content), "old-model")]
    )

    found = await ContentRetrievalService(
        repository, FakeEmbeddingClient("new-model")
    ).search_scenario_content("job_interview", "experience", limit=5)

    assert found == []


@pytest.mark.asyncio
async def test_the_corpus_is_empty_for_a_model_nothing_was_embedded_with(
    session: AsyncSession,
) -> None:
    service = ContentCorpusService(ContentChunkRepositoryImpl(session))
    assert await service.is_empty_for("embedding-model")

    await _store_rule(session, "articles")

    assert not await service.is_empty_for("embedding-model")
    assert await service.is_empty_for("new-model")
