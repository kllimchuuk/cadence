from langgraph.runtime import Runtime

from orchestration.context import AnalysisRuntimeContext
from orchestration.state import AnalysisState
from practice.repository import LearningSessionRepositoryImpl
from weaknesses.repository import WeaknessRecordRepositoryImpl
from weaknesses.service import WeaknessService
from weaknesses.skill_keys import category_of


async def weakness_state_update_node(
    state: AnalysisState, *, runtime: Runtime[AnalysisRuntimeContext]
) -> dict[str, object]:
    async with runtime.context.session_factory() as session:
        weakness_service = WeaknessService(
            WeaknessRecordRepositoryImpl(session),
            LearningSessionRepositoryImpl(session),
        )

        for observation in state["skill_observations"]:
            category = category_of(observation["skill_key"])
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
