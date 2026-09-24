import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.service import AnalysisService
from orchestration.graph import build_session_graph
from orchestration.schemas import SessionAnalysisResult, SkillObservation
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
async def test_session_analysis_writes_a_real_analysis_row(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")
    analysis_service = AnalysisService(
        SessionAnalysisRepositoryImpl(session), LearningSessionRepositoryImpl(session)
    )

    graph = build_session_graph()
    config = {
        "configurable": {
            "briefing_llm": _FakeLLMClient("Hi, thanks for joining!"),
            "conversing_llm": _FakeLLMClient("That's a great start — tell me more."),
            "session_analysis_llm": _FakeStructuredLLMClient(
                SessionAnalysisResult(
                    grammar_findings=[{"note": "past tense slip"}],
                    vocabulary_findings=[],
                    fluency_findings={"filler_word_count": 2},
                    task_completion={"completed_items": ["greet the interviewer"]},
                    focus_points=["Practice past-tense verbs"],
                    skill_observations=[
                        SkillObservation(
                            category="grammar",
                            skill_key="past_simple",
                            outcome="error",
                            note="Used present tense for a past event.",
                        )
                    ],
                    new_facts=["User is preparing for a backend interview."],
                )
            ),
            "analysis_service": analysis_service,
        }
    }

    await graph.ainvoke(
        {
            "session_id": learning_session.id,
            "user_id": user_id,
            "scenario_id": "job_interview",
            "transcript": [],
            "turn_count": 0,
            "should_exit": False,
        },
        config=config,
    )

    stored = await analysis_service.get_analysis(learning_session.id, user_id)
    assert stored is not None
    assert stored.focus_points == ["Practice past-tense verbs"]
    assert stored.grammar_findings == [{"note": "past tense slip"}]
