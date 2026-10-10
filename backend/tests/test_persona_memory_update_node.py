import uuid

import pytest
import pytest_asyncio
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph
from orchestration.nodes import conversing as conversing_node_module
from orchestration.state import initial_session_state
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from users.repository import UserRepositoryImpl

from tests.fakes import FakeLLMClient, analysis_result
from tests.helpers import run_graph_to_completion


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


@pytest.mark.asyncio
async def test_persona_memory_update_writes_real_facts(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conversing_node_module, "MAX_CONVERSATION_TURNS", 1)

    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")

    graph = build_session_graph(checkpointer=InMemorySaver())
    context = SessionRuntimeContext(
        briefing_llm=FakeLLMClient("Hi, thanks for joining!"),
        conversing_llm=FakeLLMClient("That's a great start — tell me more."),
        session_analysis_llm=FakeLLMClient(
            analysis=analysis_result(
                new_facts=["User is preparing for a backend interview."]
            )
        ),
        session_factory=session_factory,
    )

    await run_graph_to_completion(
        graph,
        initial_session_state(learning_session.id, user_id, "job_interview"),
        context,
        {"configurable": {"thread_id": str(uuid.uuid4())}},
        user_turns=["Sure."],
    )

    persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
    memory = await persona_service.get_memory(user_id, "job_interview")
    assert memory is not None
    assert memory.facts == ["User is preparing for a backend interview."]
