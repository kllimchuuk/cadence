import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph
from orchestration.schemas import SessionAnalysisResult, SkillObservation
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from users.repository import UserRepositoryImpl
from weaknesses.models import WeaknessCategory, WeaknessState
from weaknesses.repository import WeaknessRecordRepositoryImpl


class _FakeLLMClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def generate(self, _prompt: str) -> str:
        return self._reply

    async def generate_structured(self, prompt: str, schema: type) -> object:
        raise NotImplementedError()


class _FakeStructuredLLMClient:
    def __init__(self, result: SessionAnalysisResult) -> None:
        self._result = result

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError()

    async def generate_structured(
        self, prompt: str, schema: type
    ) -> SessionAnalysisResult:
        return self._result


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
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")

    graph = build_session_graph()
    context = SessionRuntimeContext(
        briefing_llm=_FakeLLMClient("Hi, thanks for joining!"),
        conversing_llm=_FakeLLMClient("That's a great start — tell me more."),
        session_analysis_llm=_FakeStructuredLLMClient(
            SessionAnalysisResult(
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

    await graph.ainvoke(
        {
            "session_id": learning_session.id,
            "user_id": user_id,
            "scenario_id": "job_interview",
            "transcript": [],
            "turn_count": 0,
            "should_exit": False,
        },
        context=context,
    )

    weakness_repository = WeaknessRecordRepositoryImpl(session)
    record = await weakness_repository.get_by_user_and_skill(
        user_id, WeaknessCategory.GRAMMAR, "past_simple"
    )
    assert record is not None
    assert record.state == WeaknessState.ACTIVE
    assert record.last_session_id == learning_session.id
