import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph
from orchestration.schemas import SessionAnalysisResult
from practice.models import SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from users.repository import UserRepositoryImpl


class _FakeLLMClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def generate(self, _prompt: str) -> str:
        return self._reply

    async def generate_structured(self, prompt: str, schema: type) -> object:
        raise NotImplementedError()


class _FakeStructuredLLMClient:
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError()

    async def generate_structured(
        self, prompt: str, schema: type
    ) -> SessionAnalysisResult:
        return SessionAnalysisResult(
            grammar_findings=[],
            vocabulary_findings=[],
            fluency_findings={},
            task_completion={},
            focus_points=["Practice past-tense verbs"],
            skill_observations=[],
            new_facts=[],
        )


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
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")
    session_id = learning_session.id

    graph = build_session_graph()
    context = SessionRuntimeContext(
        briefing_llm=_FakeLLMClient("Hi, thanks for joining!"),
        conversing_llm=_FakeLLMClient("That's a great start — tell me more."),
        session_analysis_llm=_FakeStructuredLLMClient(),
        session_factory=session_factory,
    )

    await graph.ainvoke(
        {
            "session_id": session_id,
            "user_id": user_id,
            "scenario_id": "job_interview",
            "transcript": [],
            "turn_count": 0,
            "should_exit": False,
        },
        context=context,
    )

    session.expire_all()
    finished = await practice_service.get_session(session_id, user_id)
    assert finished.status == SessionStatus.COMPLETED
    assert finished.ended_at is not None
    assert finished.transcript is not None and len(finished.transcript) > 0
