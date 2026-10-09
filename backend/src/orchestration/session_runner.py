import uuid
from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import SessionRuntimeContext
from orchestration.graph import RECURSION_LIMIT_PER_TURN
from orchestration.nodes.conversing import END_SESSION_REQUEST
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

    async def end_conversation(self, learning_session: LearningSession) -> SessionTurn:
        if not await self._learner_has_spoken(learning_session):
            await self.abandon_session(learning_session)
            return SessionTurn(assistant_messages=(), awaiting_user=False)
        return await self._advance(
            learning_session, Command(resume=END_SESSION_REQUEST)
        )

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
        await self._forget(learning_session)

    async def _advance(
        self, learning_session: LearningSession, graph_input: Any
    ) -> SessionTurn:
        delivered_entries = len(await self._checkpointed_transcript(learning_session))
        result = await self._graph.ainvoke(
            graph_input,
            context=self._runtime_context,
            config=self._config(learning_session),
        )
        turn = self._turn_from(result, delivered_entries)
        if not turn.awaiting_user:
            await self._forget(learning_session)
        return turn

    async def _forget(self, learning_session: LearningSession) -> None:
        await self._graph.checkpointer.adelete_thread(self._thread_id(learning_session))

    async def _learner_has_spoken(self, learning_session: LearningSession) -> bool:
        checkpointed_state = await self._checkpointed_state(learning_session)
        return checkpointed_state.get("turn_count", 0) > 0

    async def _checkpointed_transcript(
        self, learning_session: LearningSession
    ) -> list[dict[str, str]]:
        checkpointed_state = await self._checkpointed_state(learning_session)
        return checkpointed_state.get("transcript", [])

    async def _checkpointed_state(
        self, learning_session: LearningSession
    ) -> dict[str, Any]:
        snapshot = await self._graph.aget_state(self._config(learning_session))
        return snapshot.values

    @classmethod
    def _config(cls, learning_session: LearningSession) -> dict[str, object]:
        return {
            "configurable": {"thread_id": cls._thread_id(learning_session)},
            "recursion_limit": RECURSION_LIMIT_PER_TURN,
        }

    @staticmethod
    def _thread_id(learning_session: LearningSession) -> str:
        return str(learning_session.id)

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
