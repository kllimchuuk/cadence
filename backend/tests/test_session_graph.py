import uuid

import pytest

from orchestration.graph import build_session_graph


@pytest.mark.asyncio
async def test_the_graph_runs_briefing_then_conversing_once() -> None:
    graph = build_session_graph()

    result = await graph.ainvoke(
        {
            "session_id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "scenario_id": "job_interview",
            "transcript": [],
            "turn_count": 0,
        }
    )

    assert [entry["role"] for entry in result["transcript"]] == [
        "assistant",
        "user",
        "assistant",
    ]
    assert result["turn_count"] == 1
