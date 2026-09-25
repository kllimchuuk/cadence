import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from llm.exceptions import LLMResponseError
from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph
from orchestration.schemas import SessionAnalysisResult, SkillObservation
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from scenarios.config import get_scenario
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


class _FlakyLLMClient:
    def __init__(self, reply: str, fail_times: int) -> None:
        self._reply = reply
        self._fail_times = fail_times
        self.call_count = 0

    async def generate(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise LLMResponseError("transient failure")
        return self._reply

    async def generate_structured(self, prompt: str, schema: type) -> object:
        raise NotImplementedError()


class _FakeStructuredLLMClient:
    def __init__(self, result: SessionAnalysisResult) -> None:
        self._result = result
        self.received_prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError()

    async def generate_structured(
        self, prompt: str, schema: type
    ) -> SessionAnalysisResult:
        self.received_prompts.append(prompt)
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


@pytest.mark.asyncio
async def test_briefing_and_conversing_prompts_include_remembered_persona_facts(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")

    persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
    await persona_service.remember(
        user_id, "job_interview", ["User is preparing for a backend interview."]
    )

    graph = build_session_graph()
    briefing_llm = _FakeLLMClient("Hi again!")
    conversing_llm = _FakeLLMClient("Great, let's continue.")

    await graph.ainvoke(
        _initial_state(learning_session.id, user_id),
        context=_context(session_factory, briefing_llm, conversing_llm),
    )

    assert briefing_llm.received_prompts
    assert (
        "User is preparing for a backend interview." in briefing_llm.received_prompts[0]
    )
    assert conversing_llm.received_prompts
    assert (
        "User is preparing for a backend interview."
        in conversing_llm.received_prompts[0]
    )


@pytest.mark.asyncio
async def test_session_analysis_prompt_includes_the_scenarios_goal_checklist(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")
    scenario = get_scenario("job_interview")

    session_analysis_llm = _FakeStructuredLLMClient(_default_analysis_result())
    context = SessionRuntimeContext(
        briefing_llm=_FakeLLMClient("hi"),
        conversing_llm=_FakeLLMClient("hi"),
        session_analysis_llm=session_analysis_llm,
        session_factory=session_factory,
    )

    graph = build_session_graph()
    await graph.ainvoke(
        _initial_state(learning_session.id, user_id),
        context=context,
    )

    assert session_analysis_llm.received_prompts
    prompt = session_analysis_llm.received_prompts[0]
    for goal in scenario.goal_checklist:
        assert goal in prompt


@pytest.mark.asyncio
async def test_briefing_recovers_from_a_transient_llm_failure(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")

    graph = build_session_graph()
    briefing_llm = _FlakyLLMClient("Hi, thanks for joining!", fail_times=2)
    conversing_llm = _FakeLLMClient("continuing")

    result = await graph.ainvoke(
        _initial_state(learning_session.id, user_id),
        context=_context(session_factory, briefing_llm, conversing_llm),
    )

    assert briefing_llm.call_count == 3
    assert result["transcript"][0] == {
        "role": "assistant",
        "content": "Hi, thanks for joining!",
    }


@pytest.mark.asyncio
async def test_briefing_gives_up_after_exhausting_retries(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> None:
    practice_service = PracticeService(LearningSessionRepositoryImpl(session))
    learning_session = await practice_service.start_session(user_id, "job_interview")

    graph = build_session_graph()
    briefing_llm = _FlakyLLMClient("never used", fail_times=99)

    with pytest.raises(LLMResponseError):
        await graph.ainvoke(
            _initial_state(learning_session.id, user_id),
            context=_context(session_factory, briefing_llm, _FakeLLMClient("hi")),
        )

    assert briefing_llm.call_count == 3
