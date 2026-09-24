from langchain_core.runnables import RunnableConfig

from orchestration.state import SessionState
from weaknesses.models import WeaknessCategory
from weaknesses.service import WeaknessService


async def weakness_state_update_node(
    state: SessionState, config: RunnableConfig
) -> dict[str, object]:
    weakness_service: WeaknessService = config["configurable"]["weakness_service"]

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

    return {}
