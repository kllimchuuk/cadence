import logging
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.context import AnalysisRuntimeContext
from orchestration.exceptions import SessionAnalysisFailedError
from orchestration.state import initial_analysis_state
from practice.models import AnalysisStatus, LearningSession
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService

logger = logging.getLogger(__name__)


class SessionAnalysisRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        runtime_context: AnalysisRuntimeContext,
        graph: CompiledStateGraph,
    ) -> None:
        self._session_factory = session_factory
        self._runtime_context = runtime_context
        self._graph = graph

    async def analyse(self, learning_session: LearningSession) -> tuple[str, ...]:
        try:
            result = await self._run_graph(learning_session)
        except Exception as error:
            logger.exception(
                "Session analysis failed",
                extra={"session_id": str(learning_session.id)},
            )
            await self._record(learning_session, AnalysisStatus.FAILED)
            raise SessionAnalysisFailedError() from error

        await self._record(learning_session, AnalysisStatus.COMPLETED)
        return tuple(result["focus_points"])

    async def _run_graph(self, learning_session: LearningSession) -> dict[str, Any]:
        finished = await self._finished_session(learning_session)
        return await self._graph.ainvoke(
            initial_analysis_state(
                finished.id, finished.user_id, finished.scenario_id, finished.transcript
            ),
            context=self._runtime_context,
        )

    async def _finished_session(
        self, learning_session: LearningSession
    ) -> LearningSession:
        async with self._session_factory() as session:
            practice_service = PracticeService(LearningSessionRepositoryImpl(session))
            return await practice_service.get_session(
                learning_session.id, learning_session.user_id
            )

    async def _record(
        self, learning_session: LearningSession, analysis_status: AnalysisStatus
    ) -> None:
        try:
            async with self._session_factory() as session:
                practice_service = PracticeService(
                    LearningSessionRepositoryImpl(session)
                )
                await practice_service.record_analysis_status(
                    learning_session.id, learning_session.user_id, analysis_status
                )
                await session.commit()
        except Exception:
            logger.exception(
                "Could not record the analysis status",
                extra={
                    "session_id": str(learning_session.id),
                    "analysis_status": analysis_status,
                },
            )
