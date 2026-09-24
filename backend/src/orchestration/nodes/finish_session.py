from langchain_core.runnables import RunnableConfig

from orchestration.state import SessionState
from practice.models import SessionStatus
from practice.service import PracticeService


async def finish_session_node(
    state: SessionState, config: RunnableConfig
) -> dict[str, object]:
    practice_service: PracticeService = config["configurable"]["practice_service"]
    await practice_service.finish_session(
        state["session_id"],
        state["user_id"],
        SessionStatus.COMPLETED,
        state["transcript"],
    )
    return {}
