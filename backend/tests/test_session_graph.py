import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph
from orchestration.schemas import SessionAnalysisResult, SkillObservation
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from users.repository import UserRepositoryImpl


class _FakeLLMClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.received_prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.received_prompts.append(prompt)
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


def _default_analysis_result() -> SessionAnalysisResult:
    return SessionAnalysisResult(
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
        new_facts=["User is preparing for a backend interview."],
    )


def _context(
    session_factory: async_sessionmaker[AsyncSession],
    briefing_llm: _FakeLLMClient,
    conversing_llm: _FakeLLMClient,
    analysis_result: SessionAnalysisResult | None = None,
) -> SessionRuntimeContext:
    return SessionRuntimeContext(
        briefing_llm=briefing_llm,
        conversing_llm=conversing_llm,
        session_analysis_llm=_FakeStructuredLLMClient(
            analysis_result or _default_analysis_result()
        ),
        session_factory=session_factory,
    )


def _initial_state(session_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, object]:
    return {
        "session_id": session_id,
        "user_id": user_id,
        "scenario_id": "job_interview",
        "transcript": [],
        "turn_count": 0,
        "should_exit": False,
    }


@pytest.mark.asyncio
async def test_conversing_loops_until_should_exit_then_wraps_up(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")

    graph = build_session_graph()
    briefing_llm = _FakeLLMClient("Hi, thanks for joining!")
    conversing_llm = _FakeLLMClient("That's a great start — tell me more.")

    result = await graph.ainvoke(
        _initial_state(learning_session.id, user_id),
        context=_context(session_factory, briefing_llm, conversing_llm),
    )

    assert [entry["role"] for entry in result["transcript"]] == [
        "assistant",
        "user",
        "assistant",
        "user",
        "assistant",
        "assistant",
    ]
    assert result["turn_count"] == 2
    assert result["should_exit"] is True


@pytest.mark.asyncio
async def test_conversing_uses_the_injected_llm_reply_not_a_hardcoded_one(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")

    graph = build_session_graph()
    briefing_llm = _FakeLLMClient("injected briefing line")
    conversing_llm = _FakeLLMClient("injected conversing reply")

    result = await graph.ainvoke(
        _initial_state(learning_session.id, user_id),
        context=_context(session_factory, briefing_llm, conversing_llm),
    )

    assert result["transcript"][0] == {
        "role": "assistant",
        "content": "injected briefing line",
    }
    assert result["transcript"][2] == {
        "role": "assistant",
        "content": "injected conversing reply",
    }
    assert (
        conversing_llm.received_prompts
    ), "conversing_node never called its llm_client"


@pytest.mark.asyncio
async def test_session_analysis_forwards_its_findings_to_downstream_nodes(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")

    graph = build_session_graph()
    result = await graph.ainvoke(
        _initial_state(learning_session.id, user_id),
        context=_context(
            session_factory,
            _FakeLLMClient("hi"),
            _FakeLLMClient("hi"),
        ),
    )

    assert result["skill_observations"] == [
        {
            "category": "grammar",
            "skill_key": "past_simple",
            "outcome": "error",
            "note": "Used present tense for a past event.",
        }
    ]
    assert result["persona_facts"] == ["User is preparing for a backend interview."]


@pytest.mark.asyncio
async def test_persona_memory_update_skips_the_service_when_there_are_no_new_facts(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")
    analysis_result = SessionAnalysisResult(
        grammar_findings=[],
        vocabulary_findings=[],
        fluency_findings={},
        task_completion={},
        focus_points=["Practice past-tense verbs"],
        skill_observations=[],
        new_facts=[],
    )

    graph = build_session_graph()
    await graph.ainvoke(
        _initial_state(learning_session.id, user_id),
        context=_context(
            session_factory,
            _FakeLLMClient("hi"),
            _FakeLLMClient("hi"),
            analysis_result=analysis_result,
        ),
    )

    persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
    memory = await persona_service.get_memory(user_id, "job_interview")
    assert memory is None
