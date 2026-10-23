import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rag.entries import ContentEntry, EmbeddedEntry
from rag.models import Corpus
from rag.repository import ContentChunkRepositoryImpl
from rag.service import GrammarReferenceService

from tests.fakes import fake_embedding


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
