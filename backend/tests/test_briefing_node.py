import uuid

import pytest
import pytest_asyncio
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import ConversationRuntimeContext
from orchestration.graph import build_conversation_graph
from orchestration.nodes.briefing import SCENARIO_CONTENT_LIMIT
from orchestration.nodes.conversing import END_SESSION_REQUEST
from orchestration.state import initial_conversation_state
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from rag.entries import ContentEntry, EmbeddedEntry
from rag.models import Corpus
from rag.repository import ContentChunkRepositoryImpl
from users.repository import UserRepositoryImpl

from tests.fakes import FakeEmbeddingClient, FakeLLMClient, fake_embedding
from tests.helpers import run_graph_to_completion

MODEL = "embedding-model"


@pytest_asyncio.fixture
async def user_id(session: AsyncSession) -> uuid.UUID:
    user = await UserRepositoryImpl(session).create(
        email="learner@cadence.test",
        first_name="Learner",
        last_name="One",
        nickname="learner",
        hashed_password="hashed",
    )
    return user.id


async def _store(session: AsyncSession, scenario_id: str, title: str, content: str):
    entry = ContentEntry(
        corpus=Corpus.SCENARIO_CONTENT,
        scenario_id=scenario_id,
        title=title,
        content=content,
    )
    await ContentChunkRepositoryImpl(session).upsert_many(
        [EmbeddedEntry(entry, fake_embedding(f"{title} {content}"), MODEL)]
    )


async def _run_briefing(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    embedder: FakeEmbeddingClient,
) -> dict[str, object]:
    learning_session = await PracticeService(
        LearningSessionRepositoryImpl(session)
    ).start_session(user_id, "job_interview")
    context = ConversationRuntimeContext(
        briefing_llm=FakeLLMClient("Hi!"),
        conversing_llm=FakeLLMClient("Go on."),
        embedder=embedder,
        session_factory=session_factory,
    )
    return await run_graph_to_completion(
        build_conversation_graph(checkpointer=InMemorySaver()),
        initial_conversation_state(learning_session.id, user_id, "job_interview"),
        context,
        {"configurable": {"thread_id": str(uuid.uuid4())}},
        user_turns=[END_SESSION_REQUEST],
    )


@pytest.mark.asyncio
async def test_briefing_puts_retrieved_scenario_content_into_the_system_prompt(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    await _store(session, "job_interview", "Experience", "ask about experience")
    await _store(session, "daily_standup", "Blockers", "ask about blockers")

    result = await _run_briefing(
        session, session_factory, user_id, FakeEmbeddingClient()
    )

    assert "- Experience: ask about experience" in result["system_prompt"]
    assert "Blockers" not in result["system_prompt"]


@pytest.mark.asyncio
async def test_briefing_queries_with_the_remembered_facts_and_the_scenario_goals(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    await PersonaService(PersonaMemoryRepositoryImpl(session)).remember(
        user_id, "job_interview", ["User is moving from backend into AI."]
    )
    embedder = FakeEmbeddingClient()

    await _run_briefing(session, session_factory, user_id, embedder)

    assert len(embedder.queries) == 1
    assert "User is moving from backend into AI." in embedder.queries[0]
    assert "ask about the candidate's relevant experience" in embedder.queries[0]


@pytest.mark.asyncio
async def test_briefing_retrieves_at_most_the_configured_number_of_entries(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    for number in range(SCENARIO_CONTENT_LIMIT + 2):
        await _store(session, "job_interview", f"Entry {number}", "question")

    result = await _run_briefing(
        session, session_factory, user_id, FakeEmbeddingClient()
    )

    assert result["system_prompt"].count("- Entry ") == SCENARIO_CONTENT_LIMIT


@pytest.mark.asyncio
async def test_briefing_embeds_the_query_once_per_session_not_per_turn(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    embedder = FakeEmbeddingClient()

    await _run_briefing(session, session_factory, user_id, embedder)

    assert len(embedder.queries) == 1
