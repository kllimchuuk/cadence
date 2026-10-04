import uuid
from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import SessionRuntimeContext
from orchestration.graph import recursion_limit_for_turn
from orchestration.state import initial_session_state
from practice.models import LearningSession, SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService

_INTERRUPT_KEY = "__interrupt__"
_ASSISTANT_ROLE = "assistant"


@dataclass(frozen=True)
class SessionTurn:
    assistant_messages: tuple[str, ...]
    awaiting_user: bool
    focus_points: tuple[str, ...] = ()


class SessionRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        runtime_context: SessionRuntimeContext,
        graph: CompiledStateGraph,
    ) -> None:
        self._session_factory = session_factory
        self._runtime_context = runtime_context
        self._graph = graph

    async def create_session(
        self, user_id: uuid.UUID, scenario_id: str
    ) -> LearningSession:
        async with self._session_factory() as session:
            practice_service = PracticeService(LearningSessionRepositoryImpl(session))
            learning_session = await practice_service.start_session(
                user_id, scenario_id
            )
            await session.commit()
            return learning_session

    async def open_conversation(self, learning_session: LearningSession) -> SessionTurn:
        return await self._advance(
            learning_session,
            initial_session_state(
                learning_session.id,
                learning_session.user_id,
                learning_session.scenario_id,
            ),
        )

    async def submit_turn(
        self, learning_session: LearningSession, user_turn: str
    ) -> SessionTurn:
        return await self._advance(learning_session, Command(resume=user_turn))

    async def abandon_session(self, learning_session: LearningSession) -> None:
        transcript = await self._checkpointed_transcript(learning_session)
        async with self._session_factory() as session:
            practice_service = PracticeService(LearningSessionRepositoryImpl(session))
            await practice_service.finish_session(
                learning_session.id,
                learning_session.user_id,
                SessionStatus.INCOMPLETE,
                transcript,
            )
            await session.commit()

    async def _advance(
        self, learning_session: LearningSession, graph_input: Any
    ) -> SessionTurn:
        delivered_entries = len(await self._checkpointed_transcript(learning_session))
        result = await self._graph.ainvoke(
            graph_input,
            context=self._runtime_context,
            config=self._config(learning_session),
        )
        return self._turn_from(result, delivered_entries)

    async def _checkpointed_transcript(
        self, learning_session: LearningSession
    ) -> list[dict[str, str]]:
        snapshot = await self._graph.aget_state(self._config(learning_session))
        return snapshot.values.get("transcript", [])

    @staticmethod
    def _config(learning_session: LearningSession) -> dict[str, object]:
        return {
            "configurable": {"thread_id": str(learning_session.id)},
            "recursion_limit": recursion_limit_for_turn(),
        }

    @staticmethod
    def _turn_from(result: dict[str, Any], delivered_entries: int) -> SessionTurn:
        new_entries = result["transcript"][delivered_entries:]
        awaiting_user = _INTERRUPT_KEY in result
        return SessionTurn(
            assistant_messages=tuple(
                entry["content"]
                for entry in new_entries
                if entry["role"] == _ASSISTANT_ROLE
            ),
            awaiting_user=awaiting_user,
            focus_points=tuple(result["focus_points"]),
        )
