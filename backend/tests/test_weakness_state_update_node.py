import uuid

import pytest
import pytest_asyncio
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph
from orchestration.nodes import conversing as conversing_node_module
from orchestration.schemas import SessionAnalysisResult, SkillObservation
from orchestration.state import initial_session_state
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from users.repository import UserRepositoryImpl
from weaknesses.models import WeaknessCategory, WeaknessState
from weaknesses.repository import WeaknessRecordRepositoryImpl

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
async def test_weakness_state_update_writes_a_real_weakness_record(
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
            analysis=SessionAnalysisResult(
                grammar_findings=[],
                vocabulary_findings=[],
                fluency_findings={},
                task_completion={},
                focus_points=["Practice past-tense verbs"],
                skill_observations=[
                    SkillObservation(
                        category="grammar",
                        skill_key="past_simple",
                        outcome="error",
                        note="Used present tense for a past event.",
                    )
                ],
                new_facts=[],
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

    weakness_repository = WeaknessRecordRepositoryImpl(session)
    record = await weakness_repository.get_by_user_and_skill(
        user_id, WeaknessCategory.GRAMMAR, "past_simple"
    )
    assert record is not None
    assert record.state == WeaknessState.ACTIVE
    assert record.last_session_id == learning_session.id
