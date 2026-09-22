import uuid

import pytest

from orchestration.graph import build_session_graph


class _FakeLLMClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.received_prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.received_prompts.append(prompt)
        return self._reply


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
    briefing_llm: _FakeLLMClient, conversing_llm: _FakeLLMClient
) -> dict[str, object]:
    return {
        "configurable": {"briefing_llm": briefing_llm, "conversing_llm": conversing_llm}
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
