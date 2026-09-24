import uuid

import pytest

from orchestration.graph import build_session_graph
from orchestration.schemas import SessionAnalysisResult, SkillObservation
from weaknesses.models import WeaknessCategory


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


class _FakeAnalysisService:
    def __init__(self) -> None:
        self.created_with: dict[str, object] | None = None

    async def create_analysis(self, **kwargs: object) -> None:
        self.created_with = kwargs


class _FakeWeaknessService:
    def __init__(self) -> None:
        self.errors: list[tuple[object, ...]] = []
        self.clean_uses: list[tuple[object, ...]] = []

    async def record_error(
        self,
        user_id: uuid.UUID,
        category: WeaknessCategory,
        skill_key: str,
        session_id: uuid.UUID,
    ) -> None:
        self.errors.append((user_id, category, skill_key, session_id))

    async def record_clean_use(
        self,
        user_id: uuid.UUID,
        category: WeaknessCategory,
        skill_key: str,
        session_id: uuid.UUID,
    ) -> None:
        self.clean_uses.append((user_id, category, skill_key, session_id))


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


def _initial_state() -> dict[str, object]:
    return {
        "session_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "scenario_id": "job_interview",
        "transcript": [],
        "turn_count": 0,
        "should_exit": False,
    }


def _config(
    briefing_llm: _FakeLLMClient,
    conversing_llm: _FakeLLMClient,
    analysis_service: _FakeAnalysisService | None = None,
    analysis_result: SessionAnalysisResult | None = None,
    weakness_service: _FakeWeaknessService | None = None,
) -> dict[str, object]:
    return {
        "configurable": {
            "briefing_llm": briefing_llm,
            "conversing_llm": conversing_llm,
            "session_analysis_llm": _FakeStructuredLLMClient(
                analysis_result or _default_analysis_result()
            ),
            "analysis_service": analysis_service or _FakeAnalysisService(),
            "weakness_service": weakness_service or _FakeWeaknessService(),
        }
    }


@pytest.mark.asyncio
async def test_conversing_loops_until_should_exit_then_wraps_up() -> None:
    graph = build_session_graph()
    briefing_llm = _FakeLLMClient("Hi, thanks for joining!")
    conversing_llm = _FakeLLMClient("That's a great start — tell me more.")

    result = await graph.ainvoke(
        _initial_state(), config=_config(briefing_llm, conversing_llm)
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
async def test_conversing_uses_the_injected_llm_reply_not_a_hardcoded_one() -> None:
    graph = build_session_graph()
    briefing_llm = _FakeLLMClient("injected briefing line")
    conversing_llm = _FakeLLMClient("injected conversing reply")

    result = await graph.ainvoke(
        _initial_state(), config=_config(briefing_llm, conversing_llm)
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
async def test_session_analysis_records_the_analysis_and_forwards_its_findings() -> (
    None
):
    graph = build_session_graph()
    analysis_service = _FakeAnalysisService()
    state = _initial_state()

    result = await graph.ainvoke(
        state,
        config=_config(
            _FakeLLMClient("hi"),
            _FakeLLMClient("hi"),
            analysis_service=analysis_service,
        ),
    )

    assert analysis_service.created_with == {
        "session_id": state["session_id"],
        "user_id": state["user_id"],
        "grammar_findings": [],
        "vocabulary_findings": [],
        "fluency_findings": {},
        "task_completion": {},
        "focus_points": ["Practice past-tense verbs"],
    }
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
async def test_weakness_state_update_routes_observations_by_outcome() -> None:
    graph = build_session_graph()
    weakness_service = _FakeWeaknessService()
    state = _initial_state()
    analysis_result = SessionAnalysisResult(
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
            ),
            SkillObservation(
                category="vocabulary",
                skill_key="business_idioms",
                outcome="clean",
                note="Used 'touch base' correctly.",
            ),
        ],
        new_facts=[],
    )

    await graph.ainvoke(
        state,
        config=_config(
            _FakeLLMClient("hi"),
            _FakeLLMClient("hi"),
            analysis_result=analysis_result,
            weakness_service=weakness_service,
        ),
    )

    assert weakness_service.errors == [
        (state["user_id"], WeaknessCategory.GRAMMAR, "past_simple", state["session_id"])
    ]
    assert weakness_service.clean_uses == [
        (
            state["user_id"],
            WeaknessCategory.VOCABULARY,
            "business_idioms",
            state["session_id"],
        )
    ]
