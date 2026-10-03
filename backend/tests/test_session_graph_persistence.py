import asyncio
import uuid

import pytest
from alembic import command
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from core.database import build_engine, build_session_factory, psycopg_dsn
from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph, recursion_limit_for_turn
from orchestration.nodes.conversing import MAX_CONVERSATION_TURNS
from orchestration.schemas import SessionAnalysisResult
from orchestration.state import initial_session_state
from practice.models import SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from users.repository import UserRepositoryImpl

from tests.helpers import alembic_config, run_graph_to_completion


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


@pytest.mark.asyncio
async def test_a_finished_session_is_readable_from_a_fresh_checkpointer(
    throwaway_database: str,
) -> None:
    await asyncio.to_thread(command.upgrade, alembic_config(throwaway_database), "head")

    dsn = psycopg_dsn(throwaway_database)
    thread_id = str(uuid.uuid4())

    engine = build_engine(throwaway_database)
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
            initial_state = initial_session_state(
                learning_session.id, user.id, "job_interview"
            )

            async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
                await checkpointer.setup()
                graph = build_session_graph(checkpointer=checkpointer)
                invoked_result = await run_graph_to_completion(
                    graph,
                    initial_state,
                    context,
                    config={
                        "configurable": {"thread_id": thread_id},
                        "recursion_limit": recursion_limit_for_turn(),
                    },
                    user_turns=["Sounds good." for _ in range(MAX_CONVERSATION_TURNS)],
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
