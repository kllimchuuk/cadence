import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.engine import make_url

from core.database import build_engine, build_session_factory
from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph
from orchestration.schemas import SessionAnalysisResult
from practice.models import SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from users.repository import UserRepositoryImpl


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


def _psycopg_dsn(database_url: str) -> str:
    return (
        make_url(database_url)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )


@pytest.mark.asyncio
async def test_a_finished_session_is_readable_from_a_fresh_checkpointer(
    migrated_schema: str,
) -> None:
    dsn = _psycopg_dsn(migrated_schema)
    thread_id = str(uuid.uuid4())

    engine = build_engine(migrated_schema)
    session_factory = build_session_factory(engine)
    try:
        async with session_factory() as setup_session:
            user = await UserRepositoryImpl(setup_session).create(
                email="learner@cadence.test",
                first_name="Learner",
                last_name="One",
                nickname="learner",
                hashed_password="hashed",
            )
            learning_session = await LearningSessionRepositoryImpl(
                setup_session
            ).create(user.id, "job_interview")
            await setup_session.commit()

        try:
            context = SessionRuntimeContext(
                briefing_llm=_FakeLLMClient("Hi, thanks for joining!"),
                conversing_llm=_FakeLLMClient("That's a great start — tell me more."),
                session_analysis_llm=_FakeStructuredLLMClient(),
                session_factory=session_factory,
            )
            initial_state = {
                "session_id": learning_session.id,
                "user_id": user.id,
                "scenario_id": "job_interview",
                "transcript": [],
                "turn_count": 0,
                "should_exit": False,
            }

            async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
                await checkpointer.setup()
                graph = build_session_graph(checkpointer=checkpointer)
                invoked_result = await graph.ainvoke(
                    initial_state,
                    context=context,
                    config={"configurable": {"thread_id": thread_id}},
                )

            async with AsyncPostgresSaver.from_conn_string(
                dsn
            ) as restarted_checkpointer:
                restarted_graph = build_session_graph(
                    checkpointer=restarted_checkpointer
                )
                snapshot = await restarted_graph.aget_state(
                    {"configurable": {"thread_id": thread_id}}
                )

            async with session_factory() as verify_session:
                finished = await LearningSessionRepositoryImpl(
                    verify_session
                ).get_by_id(learning_session.id, user.id)
        finally:
            async with session_factory() as cleanup_session:
                user_repository = UserRepositoryImpl(cleanup_session)
                stored_user = await user_repository.get_by_id(user.id)
                if stored_user is not None:
                    await user_repository.delete(stored_user)
                await cleanup_session.commit()
    finally:
        await engine.dispose()

    assert snapshot.values["transcript"] == invoked_result["transcript"]
    assert snapshot.values["turn_count"] == invoked_result["turn_count"]
    assert snapshot.values["should_exit"] is True

    assert finished is not None
    assert finished.status == SessionStatus.COMPLETED
    assert finished.transcript == invoked_result["transcript"]
