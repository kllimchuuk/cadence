import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rag.entries import ContentEntry, EmbeddedEntry
from rag.models import Corpus
from rag.repository import ContentChunkRepository, ContentChunkRepositoryImpl
from tests.fakes import fake_embedding

MODEL = "embedding-model"


@pytest.fixture
def repository(session: AsyncSession) -> ContentChunkRepository:
    return ContentChunkRepositoryImpl(session)


def _scenario_entry(scenario_id: str, title: str, content: str) -> ContentEntry:
    return ContentEntry(
        corpus=Corpus.SCENARIO_CONTENT,
        scenario_id=scenario_id,
        title=title,
        content=content,
    )


def _grammar_entry(skill_key: str, content: str) -> ContentEntry:
    return ContentEntry(
        corpus=Corpus.GRAMMAR_REFERENCE,
        skill_key=skill_key,
        title=skill_key,
        content=content,
    )


def _embedded(entry: ContentEntry, model: str = MODEL) -> EmbeddedEntry:
    return EmbeddedEntry(entry, fake_embedding(f"{entry.title} {entry.content}"), model)


@pytest.mark.asyncio
async def test_upserted_entries_are_reported_with_their_embedding_model(
    repository: ContentChunkRepository,
) -> None:
    entry = _grammar_entry("articles", "Use a before consonants.")

    await repository.upsert_many([_embedded(entry)])

    assert await repository.get_embedding_models() == {entry.content_hash: MODEL}


@pytest.mark.asyncio
async def test_upserting_the_same_entry_again_updates_the_row_instead_of_duplicating(
    repository: ContentChunkRepository,
) -> None:
    entry = _grammar_entry("articles", "Use a before consonants.")
    await repository.upsert_many([_embedded(entry)])

    await repository.upsert_many([_embedded(entry, model="newer-model")])

    assert await repository.get_embedding_models() == {
        entry.content_hash: "newer-model"
    }


@pytest.mark.asyncio
async def test_upserting_nothing_is_a_no_op(
    repository: ContentChunkRepository,
) -> None:
    await repository.upsert_many([])

    assert await repository.get_embedding_models() == {}


@pytest.mark.asyncio
async def test_delete_except_removes_only_rows_outside_the_given_hashes(
    repository: ContentChunkRepository,
) -> None:
    kept = _grammar_entry("articles", "Use a before consonants.")
    dropped = _grammar_entry("modal_verbs", "Modals take the base verb.")
    await repository.upsert_many([_embedded(kept), _embedded(dropped)])

    removed = await repository.delete_except([kept.content_hash])

    assert removed == 1
    assert set(await repository.get_embedding_models()) == {kept.content_hash}


@pytest.mark.asyncio
async def test_search_returns_the_closest_entry_of_the_corpus_first(
    repository: ContentChunkRepository,
) -> None:
    articles = _grammar_entry("articles", "articles a an the countable singular noun")
    modals = _grammar_entry("modal_verbs", "modal verbs can should must base verb")
    await repository.upsert_many([_embedded(articles), _embedded(modals)])

    results = await repository.search(
        Corpus.GRAMMAR_REFERENCE,
        fake_embedding("articles a an the"),
        MODEL,
        limit=2,
    )

    assert [chunk.skill_key for chunk in results] == ["articles", "modal_verbs"]
    assert results[0].distance < results[1].distance


@pytest.mark.asyncio
async def test_search_only_looks_inside_the_requested_corpus(
    repository: ContentChunkRepository,
) -> None:
    grammar = _grammar_entry("articles", "interview questions about experience")
    scenario = _scenario_entry("job_interview", "Experience", "tell me about it")
    await repository.upsert_many([_embedded(grammar), _embedded(scenario)])

    results = await repository.search(
        Corpus.SCENARIO_CONTENT,
        fake_embedding("interview questions"),
        MODEL,
        limit=5,
    )

    assert [chunk.title for chunk in results] == ["Experience"]


@pytest.mark.asyncio
async def test_search_is_restricted_to_the_scenario_and_honours_the_limit(
    repository: ContentChunkRepository,
) -> None:
    await repository.upsert_many(
        [
            _embedded(_scenario_entry("job_interview", "Experience", "background")),
            _embedded(_scenario_entry("job_interview", "Weakness", "background")),
            _embedded(_scenario_entry("daily_standup", "Yesterday", "background")),
        ]
    )

    results = await repository.search(
        Corpus.SCENARIO_CONTENT,
        fake_embedding("background"),
        MODEL,
        limit=1,
        scenario_id="job_interview",
    )

    assert len(results) == 1
    assert results[0].title in {"Experience", "Weakness"}


@pytest.mark.asyncio
async def test_get_grammar_rules_ignores_scenario_content_and_unknown_keys(
    repository: ContentChunkRepository,
) -> None:
    await repository.upsert_many(
        [
            _embedded(_grammar_entry("articles", "a an the")),
            _embedded(_grammar_entry("modal_verbs", "can should must")),
            _embedded(_scenario_entry("job_interview", "articles", "a an the")),
        ]
    )

    rules = await repository.get_grammar_rules({"articles", "no_such_skill"})

    assert [(rule.corpus, rule.skill_key) for rule in rules] == [
        (Corpus.GRAMMAR_REFERENCE, "articles")
    ]


@pytest.mark.asyncio
async def test_search_skips_entries_built_with_another_embedding_model(
    repository: ContentChunkRepository,
) -> None:
    current = _grammar_entry("articles", "a an the")
    stale = _grammar_entry("modal_verbs", "a an the")
    await repository.upsert_many(
        [_embedded(current), _embedded(stale, model="old-model")]
    )

    results = await repository.search(
        Corpus.GRAMMAR_REFERENCE, fake_embedding("a an the"), MODEL, limit=5
    )

    assert [chunk.skill_key for chunk in results] == ["articles"]


@pytest.mark.asyncio
async def test_count_reflects_the_stored_chunks(
    repository: ContentChunkRepository,
) -> None:
    assert await repository.count() == 0

    await repository.upsert_many([_embedded(_grammar_entry("articles", "a an the"))])

    assert await repository.count() == 1
