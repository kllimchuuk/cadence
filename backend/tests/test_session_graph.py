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


@pytest.mark.asyncio
async def test_conversing_loops_until_should_exit_then_wraps_up() -> None:
    graph = build_session_graph()

    result = await graph.ainvoke(_initial_state())

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
