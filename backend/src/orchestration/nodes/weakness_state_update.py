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
            record = (
                weakness_service.record_error
                if observation["outcome"] == "error"
                else weakness_service.record_clean_use
            )
            await record(
                state["user_id"],
                category_of(observation["skill_key"]),
                observation["skill_key"],
                state["session_id"],
            )

        await session.commit()

    return {}
