import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.engine import make_url

from orchestration.graph import build_session_graph
from orchestration.schemas import SessionAnalysisResult


class _FakeLLMClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def generate(self, _prompt: str) -> str:
        return self._reply

    async def generate_structured(self, prompt: str, schema: type) -> object:
        raise NotImplementedError()


class _FakeStructuredLLMClient:
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError()

    async def generate_structured(
        self, prompt: str, schema: type
    ) -> SessionAnalysisResult:
        return SessionAnalysisResult(
            grammar_findings=[],
            vocabulary_findings=[],
            fluency_findings={},
            task_completion={},
            focus_points=["Practice past-tense verbs"],
            skill_observations=[],
            new_facts=[],
        )


class _FakeAnalysisService:
    async def create_analysis(self, **kwargs: object) -> None:
        pass


class _FakeWeaknessService:
    async def record_error(self, *args: object) -> None:
        pass

    async def record_clean_use(self, *args: object) -> None:
        pass


def _psycopg_dsn(database_url: str) -> str:
    return (
        make_url(database_url)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
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


def _config(thread_id: str) -> dict[str, object]:
    return {
        "configurable": {
            "thread_id": thread_id,
            "briefing_llm": _FakeLLMClient("Hi, thanks for joining!"),
            "conversing_llm": _FakeLLMClient("That's a great start — tell me more."),
            "session_analysis_llm": _FakeStructuredLLMClient(),
            "analysis_service": _FakeAnalysisService(),
            "weakness_service": _FakeWeaknessService(),
        }
    }


@pytest.mark.asyncio
async def test_a_finished_session_is_readable_from_a_fresh_checkpointer(
    migrated_schema: str,
) -> None:
    dsn = _psycopg_dsn(migrated_schema)
    thread_id = str(uuid.uuid4())

    async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
        await checkpointer.setup()
        graph = build_session_graph(checkpointer=checkpointer)
        invoked_result = await graph.ainvoke(
            _initial_state(), config=_config(thread_id)
        )

    async with AsyncPostgresSaver.from_conn_string(dsn) as restarted_checkpointer:
        restarted_graph = build_session_graph(checkpointer=restarted_checkpointer)
        snapshot = await restarted_graph.aget_state(
            {"configurable": {"thread_id": thread_id}}
        )

    assert snapshot.values["transcript"] == invoked_result["transcript"]
    assert snapshot.values["turn_count"] == invoked_result["turn_count"]
    assert snapshot.values["should_exit"] is True
