from langgraph.runtime import Runtime

from analysis.repository import SessionAnalysisRepositoryImpl
from orchestration.context import AnalysisRuntimeContext
from orchestration.state import AnalysisState
from practice.repository import LearningSessionRepositoryImpl
from progress.repository import SessionProgressRepositoryImpl
from progress.service import ProgressService


async def progress_update_node(
    state: AnalysisState, *, runtime: Runtime[AnalysisRuntimeContext]
) -> dict[str, object]:
    async with runtime.context.session_factory() as session:
        progress_service = ProgressService(
            SessionProgressRepositoryImpl(session),
            SessionAnalysisRepositoryImpl(session),
            LearningSessionRepositoryImpl(session),
        )
        await progress_service.record_session(state["session_id"], state["user_id"])
        await session.commit()

    return {}
