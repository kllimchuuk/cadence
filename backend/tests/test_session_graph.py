import uuid

import pytest

from orchestration.graph import build_session_graph
from orchestration.schemas import SessionAnalysisResult, SkillObservation


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
) -> dict[str, object]:
    return {
        "configurable": {
            "briefing_llm": briefing_llm,
            "conversing_llm": conversing_llm,
            "session_analysis_llm": _FakeStructuredLLMClient(
                analysis_result or _default_analysis_result()
            ),
            "analysis_service": analysis_service or _FakeAnalysisService(),
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
