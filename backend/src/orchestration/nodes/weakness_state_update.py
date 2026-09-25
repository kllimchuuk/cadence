from langgraph.runtime import Runtime

from orchestration.context import SessionRuntimeContext
from orchestration.state import SessionState
from practice.repository import LearningSessionRepositoryImpl
from weaknesses.models import WeaknessCategory
from weaknesses.repository import WeaknessRecordRepositoryImpl
from weaknesses.service import WeaknessService


async def weakness_state_update_node(
    state: SessionState, *, runtime: Runtime[SessionRuntimeContext]
) -> dict[str, object]:
    async with runtime.context.session_factory() as session:
        weakness_service = WeaknessService(
            WeaknessRecordRepositoryImpl(session),
            LearningSessionRepositoryImpl(session),
        )

        for observation in state["skill_observations"]:
            category = WeaknessCategory(observation["category"])
            if observation["outcome"] == "error":
                await weakness_service.record_error(
                    state["user_id"],
                    category,
                    observation["skill_key"],
                    state["session_id"],
                )
            else:
                await weakness_service.record_clean_use(
                    state["user_id"],
                    category,
                    observation["skill_key"],
                    state["session_id"],
                )

        await session.commit()

    return {}
