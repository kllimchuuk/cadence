import uuid

import pytest
import pytest_asyncio
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from analysis.schemas import (
    FluencyAssessment,
    GoalOutcome,
    LanguageFinding,
    PersonaFact,
    SessionAnalysisResult,
    SkillObservation,
    TaskCompletion,
)
from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.service import AnalysisService
from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph
from orchestration.nodes import conversing as conversing_node_module
from orchestration.state import initial_session_state
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
async def test_session_analysis_writes_a_real_analysis_row(
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
                grammar_findings=[
                    LanguageFinding(
                        evidence="Yesterday I go to the office.",
                        issue="Present tense for a past event.",
                        correction="Yesterday I went to the office.",
                    )
                ],
                vocabulary_findings=[],
                fluency_findings=FluencyAssessment(summary="Steady pace."),
                task_completion=TaskCompletion(
                    goals=[
                        GoalOutcome(
                            goal="greet the interviewer",
                            achieved=True,
                            evidence="Hi, nice to meet you.",
                        )
                    ]
                ),
                focus_points=["Practice past-tense verbs"],
                skill_observations=[
                    SkillObservation(
                        category="grammar",
                        skill_key="past_simple",
                        outcome="error",
                        evidence="Yesterday I go to the office.",
                        note="Used present tense for a past event.",
                    )
                ],
                new_facts=[
                    PersonaFact(
                        fact="User is preparing for a backend interview.",
                        evidence="I have a backend interview next week.",
                    )
                ],
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

    analysis_service = AnalysisService(
        SessionAnalysisRepositoryImpl(session), LearningSessionRepositoryImpl(session)
    )
    stored = await analysis_service.get_analysis(learning_session.id, user_id)
    assert stored is not None
    assert stored.focus_points == ["Practice past-tense verbs"]
    assert stored.grammar_findings == [
        {
            "evidence": "Yesterday I go to the office.",
            "issue": "Present tense for a past event.",
            "correction": "Yesterday I went to the office.",
        }
    ]
    assert stored.task_completion == {
        "goals": [
            {
                "goal": "greet the interviewer",
                "achieved": True,
                "evidence": "Hi, nice to meet you.",
            }
        ]
    }
    assert stored.skill_observations == [
        {
            "category": "grammar",
            "skill_key": "past_simple",
            "outcome": "error",
            "evidence": "Yesterday I go to the office.",
            "note": "Used present tense for a past event.",
        }
    ]
    assert stored.new_facts == [
        {
            "fact": "User is preparing for a backend interview.",
            "evidence": "I have a backend interview next week.",
        }
    ]
