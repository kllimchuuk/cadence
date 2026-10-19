from langgraph.runtime import Runtime

from orchestration.context import ConversationRuntimeContext
from orchestration.state import ConversationState
from practice.models import SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService


async def finish_session_node(
    state: ConversationState, *, runtime: Runtime[ConversationRuntimeContext]
) -> dict[str, object]:
    async with runtime.context.session_factory() as session:
        practice_service = PracticeService(LearningSessionRepositoryImpl(session))
        await practice_service.finish_session(
            state["session_id"],
            state["user_id"],
            SessionStatus.COMPLETED,
            state["transcript"],
        )
        await session.commit()

    return {}
