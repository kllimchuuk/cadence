import uuid
from dataclasses import dataclass

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.service import AnalysisService
from orchestration.context import SessionRuntimeContext
from orchestration.graph import build_session_graph, recursion_limit_for_turn
from orchestration.state import initial_session_state
from practice.models import LearningSession
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
        checkpointer: BaseCheckpointSaver,
    ) -> None:
        self._session_factory = session_factory
        self._runtime_context = runtime_context
        self._graph = build_session_graph(checkpointer=checkpointer)
        self._delivered_entries = 0

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
        result = await self._graph.ainvoke(
            initial_session_state(
                learning_session.id,
                learning_session.user_id,
                learning_session.scenario_id,
            ),
            context=self._runtime_context,
            config=self._config(learning_session),
        )
        return await self._turn_from(learning_session, result)

    async def submit_turn(
        self, learning_session: LearningSession, user_turn: str
    ) -> SessionTurn:
        result = await self._graph.ainvoke(
            Command(resume=user_turn),
            context=self._runtime_context,
            config=self._config(learning_session),
        )
        return await self._turn_from(learning_session, result)

    @staticmethod
    def _config(learning_session: LearningSession) -> dict[str, object]:
        return {
            "configurable": {"thread_id": str(learning_session.id)},
            "recursion_limit": recursion_limit_for_turn(),
        }

    async def _turn_from(
        self, learning_session: LearningSession, result: dict
    ) -> SessionTurn:
        transcript = result["transcript"]
        new_entries = transcript[self._delivered_entries :]
        self._delivered_entries = len(transcript)

        awaiting_user = _INTERRUPT_KEY in result
        return SessionTurn(
            assistant_messages=tuple(
                entry["content"]
                for entry in new_entries
                if entry["role"] == _ASSISTANT_ROLE
            ),
            awaiting_user=awaiting_user,
            focus_points=(
                () if awaiting_user else await self._focus_points(learning_session)
            ),
        )

    async def _focus_points(self, learning_session: LearningSession) -> tuple[str, ...]:
        async with self._session_factory() as session:
            analysis_service = AnalysisService(
                SessionAnalysisRepositoryImpl(session),
                LearningSessionRepositoryImpl(session),
            )
            analysis = await analysis_service.get_analysis(
                learning_session.id, learning_session.user_id
            )
        return tuple(analysis.focus_points) if analysis else ()
