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
from rag.entries import ContentEntry, EmbeddedEntry
from rag.models import Corpus
from rag.repository import ContentChunkRepositoryImpl
from scenarios.config import get_scenario
from users.repository import UserRepositoryImpl
from weaknesses.models import WeaknessCategory, WeaknessState
from weaknesses.repository import WeaknessRecordRepositoryImpl

from tests.fakes import (
    FakeLLMClient,
    SequencedAnalysisLLMClient,
    analysis_result,
    fake_embedding,
)

TRANSCRIPT = [
    {"role": "assistant", "content": "Hi, thanks for joining!"},
    {"role": "user", "content": "Yesterday I go to the office."},
    {"role": "user", "content": "I have a backend interview next week."},
    {"role": "assistant", "content": "Thanks for practising today."},
]
PAST_SIMPLE_ERROR = SkillObservation(
    skill_key="irregular_past_forms",
    outcome="error",
    evidence="Yesterday I go to the office.",
    note="Used present tense for a past event.",
)


BACKEND_INTERVIEW_FACT = PersonaFact(
    fact="User is preparing for a backend interview.",
    evidence="I have a backend interview next week.",
)
INVENTED_ERROR = SkillObservation(
    skill_key="irregular_past_forms",
    outcome="clean",
    evidence="Yesterday I went to the office.",
    note="Used the past tense correctly.",
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
        FakeLLMClient(analysis=analysis_result(new_facts=[BACKEND_INTERVIEW_FACT])),
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
                new_facts=[BACKEND_INTERVIEW_FACT],
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

    system_instruction = session_analysis_llm.requests[1].system_instruction
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

    for request in session_analysis_llm.requests:
        (message,) = request.messages
        assert message.role == MessageRole.USER
        assert json.loads(message.content) == TRANSCRIPT


async def _store_grammar_rule(
    session: AsyncSession, skill_key: str, title: str, content: str
) -> None:
    entry = ContentEntry(
        corpus=Corpus.GRAMMAR_REFERENCE,
        skill_key=skill_key,
        title=title,
        content=content,
    )
    await ContentChunkRepositoryImpl(session).upsert_many(
        [EmbeddedEntry(entry, fake_embedding(f"{title} {content}"), "embedding-model")]
    )


@pytest.mark.asyncio
async def test_session_analysis_classifies_the_grammar_before_the_full_analysis(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    llm = FakeLLMClient()

    await _analyse(session_id, user_id, session_factory, llm)

    triage, analysis = llm.requests
    assert "List every grammar skill" in triage.system_instruction
    assert "List every grammar skill" not in analysis.system_instruction


@pytest.mark.asyncio
async def test_session_analysis_grounds_the_prompt_in_the_classified_rules_only(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await _store_grammar_rule(
        session, "irregular_past_forms", "Irregular past", "go-went-gone"
    )
    await _store_grammar_rule(session, "articles", "Articles", "a, an, the")
    llm = FakeLLMClient(triaged_skill_keys=["irregular_past_forms"])

    await _analyse(session_id, user_id, session_factory, llm)

    instruction = llm.requests[1].system_instruction
    assert "- irregular_past_forms (Irregular past): go-went-gone" in instruction
    assert "articles" not in instruction


@pytest.mark.asyncio
async def test_session_analysis_always_includes_the_rules_of_tracked_skills(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await _store_grammar_rule(session, "articles", "Articles", "a, an, the")
    await WeaknessRecordRepositoryImpl(session).create(
        user_id, WeaknessCategory.GRAMMAR, "articles"
    )
    llm = FakeLLMClient(triaged_skill_keys=[])

    await _analyse(session_id, user_id, session_factory, llm)

    assert "- articles (Articles): a, an, the" in llm.requests[1].system_instruction


@pytest.mark.asyncio
async def test_session_analysis_without_classified_skills_has_no_reference_block(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    llm = FakeLLMClient(triaged_skill_keys=[])

    await _analyse(session_id, user_id, session_factory, llm)

    assert "<grammar_reference>" not in llm.requests[1].system_instruction


@pytest.mark.asyncio
async def test_session_analysis_lists_the_active_weaknesses_in_both_prompts(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await WeaknessRecordRepositoryImpl(session).create(
        user_id, WeaknessCategory.GRAMMAR, "articles"
    )
    llm = FakeLLMClient()

    await _analyse(session_id, user_id, session_factory, llm)

    for request in llm.requests:
        assert "articles (active)" in request.system_instruction


@pytest.mark.asyncio
async def test_invented_evidence_is_sent_back_and_the_corrected_analysis_is_kept(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    llm = SequencedAnalysisLLMClient(
        [
            analysis_result(skill_observations=[INVENTED_ERROR]),
            analysis_result(skill_observations=[PAST_SIMPLE_ERROR]),
        ]
    )

    result = await _analyse(session_id, user_id, session_factory, llm)

    correction = llm.requests[-1].messages[-1]
    assert "Yesterday I went to the office." in correction.content
    assert len(llm.requests[-1].messages) == 3
    assert result["skill_observations"] == [PAST_SIMPLE_ERROR.model_dump()]
    record = await WeaknessRecordRepositoryImpl(session).get_by_user_and_skill(
        user_id, WeaknessCategory.GRAMMAR, "irregular_past_forms"
    )
    assert record is not None
    assert record.state == WeaknessState.ACTIVE


@pytest.mark.asyncio
async def test_evidence_still_invented_after_the_retry_is_dropped(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    invented_fact = PersonaFact(
        fact="User lives in Berlin.", evidence="I live in Berlin."
    )
    llm = SequencedAnalysisLLMClient(
        [
            analysis_result(
                skill_observations=[INVENTED_ERROR], new_facts=[invented_fact]
            ),
            analysis_result(
                skill_observations=[INVENTED_ERROR],
                new_facts=[invented_fact, BACKEND_INTERVIEW_FACT],
            ),
        ]
    )

    result = await _analyse(session_id, user_id, session_factory, llm)

    assert result["skill_observations"] == []
    assert result["persona_facts"] == [BACKEND_INTERVIEW_FACT.fact]
    record = await WeaknessRecordRepositoryImpl(session).get_by_user_and_skill(
        user_id, WeaknessCategory.GRAMMAR, "irregular_past_forms"
    )
    assert record is None


@pytest.mark.asyncio
async def test_verified_evidence_costs_no_second_analysis_call(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    llm = FakeLLMClient(
        analysis=analysis_result(skill_observations=[PAST_SIMPLE_ERROR])
    )

    await _analyse(session_id, user_id, session_factory, llm)

    assert len(llm.requests) == 2
