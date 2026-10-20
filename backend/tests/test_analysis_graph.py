import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.schemas import (
    FluencyAssessment,
    GoalOutcome,
    LanguageFinding,
    PersonaFact,
    SessionAnalysisResult,
    SkillObservation,
    TaskCompletion,
)
from analysis.service import AnalysisService
from llm.client import MessageRole
from orchestration.context import AnalysisRuntimeContext
from orchestration.graph import build_analysis_graph
from orchestration.state import initial_analysis_state
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from scenarios.config import get_scenario
from users.repository import UserRepositoryImpl
from weaknesses.models import WeaknessCategory, WeaknessState
from weaknesses.repository import WeaknessRecordRepositoryImpl

from tests.fakes import FakeLLMClient, analysis_result

TRANSCRIPT = [
    {"role": "assistant", "content": "Hi, thanks for joining!"},
    {"role": "user", "content": "Yesterday I go to the office."},
    {"role": "assistant", "content": "Thanks for practising today."},
]
PAST_SIMPLE_ERROR = SkillObservation(
    skill_key="irregular_past_forms",
    outcome="error",
    evidence="Yesterday I go to the office.",
    note="Used present tense for a past event.",
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


@pytest_asyncio.fixture
async def session_id(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")
    return learning_session.id


async def _analyse(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    session_analysis_llm: FakeLLMClient,
) -> dict[str, object]:
    return await build_analysis_graph().ainvoke(
        initial_analysis_state(session_id, user_id, "job_interview", TRANSCRIPT),
        context=AnalysisRuntimeContext(
            session_analysis_llm=session_analysis_llm,
            session_factory=session_factory,
        ),
    )


@pytest.mark.asyncio
async def test_session_analysis_writes_a_real_analysis_row(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await _analyse(
        session_id,
        user_id,
        session_factory,
        FakeLLMClient(
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
                        skill_key="irregular_past_forms",
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
    )

    analysis_service = AnalysisService(
        SessionAnalysisRepositoryImpl(session), LearningSessionRepositoryImpl(session)
    )
    stored = await analysis_service.get_analysis(session_id, user_id)
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
            "skill_key": "irregular_past_forms",
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


@pytest.mark.asyncio
async def test_weakness_state_update_writes_a_real_weakness_record(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await _analyse(
        session_id,
        user_id,
        session_factory,
        FakeLLMClient(analysis=analysis_result(skill_observations=[PAST_SIMPLE_ERROR])),
    )

    weakness_repository = WeaknessRecordRepositoryImpl(session)
    record = await weakness_repository.get_by_user_and_skill(
        user_id, WeaknessCategory.GRAMMAR, "irregular_past_forms"
    )
    assert record is not None
    assert record.state == WeaknessState.ACTIVE
    assert record.last_session_id == session_id


@pytest.mark.asyncio
async def test_persona_memory_update_writes_real_facts(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await _analyse(
        session_id,
        user_id,
        session_factory,
        FakeLLMClient(
            analysis=analysis_result(
                new_facts=["User is preparing for a backend interview."]
            )
        ),
    )

    persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
    memory = await persona_service.get_memory(user_id, "job_interview")
    assert memory is not None
    assert memory.facts == ["User is preparing for a backend interview."]


@pytest.mark.asyncio
async def test_session_analysis_forwards_its_findings_to_downstream_nodes(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    result = await _analyse(
        session_id,
        user_id,
        session_factory,
        FakeLLMClient(
            analysis=analysis_result(
                skill_observations=[PAST_SIMPLE_ERROR],
                new_facts=["User is preparing for a backend interview."],
            )
        ),
    )

    assert result["skill_observations"] == [PAST_SIMPLE_ERROR.model_dump()]
    assert result["persona_facts"] == ["User is preparing for a backend interview."]
    assert result["focus_points"] == ["Practice past-tense verbs"]


@pytest.mark.asyncio
async def test_persona_memory_update_skips_the_service_when_there_are_no_new_facts(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await _analyse(session_id, user_id, session_factory, FakeLLMClient())

    persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
    assert await persona_service.get_memory(user_id, "job_interview") is None


@pytest.mark.asyncio
async def test_session_analysis_prompt_includes_the_scenarios_goal_checklist(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    session_analysis_llm = FakeLLMClient()

    await _analyse(session_id, user_id, session_factory, session_analysis_llm)

    system_instruction = session_analysis_llm.requests[0].system_instruction
    for goal in get_scenario("job_interview").goal_checklist:
        assert goal in system_instruction


@pytest.mark.asyncio
async def test_session_analysis_receives_the_transcript_as_data(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    session_analysis_llm = FakeLLMClient()

    await _analyse(session_id, user_id, session_factory, session_analysis_llm)

    (message,) = session_analysis_llm.requests[0].messages
    assert message.role == MessageRole.USER
    assert json.loads(message.content) == TRANSCRIPT
