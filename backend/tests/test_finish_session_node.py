import uuid

import pytest
import pytest_asyncio
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph
from orchestration.nodes import conversing as conversing_node_module
from orchestration.state import initial_session_state
from practice.models import SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from users.repository import UserRepositoryImpl

from tests.fakes import FakeLLMClient
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
async def test_finish_session_closes_a_real_learning_session(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conversing_node_module, "MAX_CONVERSATION_TURNS", 1)

    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")
    session_id = learning_session.id

    graph = build_session_graph(checkpointer=InMemorySaver())
    context = SessionRuntimeContext(
        briefing_llm=FakeLLMClient("Hi, thanks for joining!"),
        conversing_llm=FakeLLMClient("That's a great start — tell me more."),
        session_analysis_llm=FakeLLMClient(),
        session_factory=session_factory,
    )

    await run_graph_to_completion(
        graph,
        initial_session_state(session_id, user_id, "job_interview"),
        context,
        {"configurable": {"thread_id": str(uuid.uuid4())}},
        user_turns=["Sure."],
    )

    session.expire_all()
    finished = await practice_service.get_session(session_id, user_id)
    assert finished.status == SessionStatus.COMPLETED
    assert finished.ended_at is not None
    assert finished.transcript is not None and len(finished.transcript) > 0
