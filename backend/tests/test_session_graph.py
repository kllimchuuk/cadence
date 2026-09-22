import uuid

import pytest

from orchestration.graph import build_session_graph


def _initial_state() -> dict[str, object]:
    return {
        "session_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "scenario_id": "job_interview",
        "transcript": [],
        "turn_count": 0,
        "should_exit": False,
    }


def _config(responder: object) -> dict[str, object]:
    return {"configurable": {"responder": responder}}


def _placeholder_responder() -> tuple[str, str]:
    return "Hello!", "That's a great start — tell me more."


@pytest.mark.asyncio
async def test_conversing_loops_until_should_exit_then_wraps_up() -> None:
    graph = build_session_graph()

    result = await graph.ainvoke(
        _initial_state(), config=_config(_placeholder_responder)
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
async def test_conversing_uses_the_injected_responder_not_a_hardcoded_one() -> None:
    graph = build_session_graph()

    def fake_responder() -> tuple[str, str]:
        return "injected user turn", "injected assistant reply"

    result = await graph.ainvoke(_initial_state(), config=_config(fake_responder))

    assert result["transcript"][1] == {"role": "user", "content": "injected user turn"}
    assert result["transcript"][2] == {
        "role": "assistant",
        "content": "injected assistant reply",
    }
