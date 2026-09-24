from langchain_core.runnables import RunnableConfig

from orchestration.state import SessionState
from persona.service import PersonaService


async def persona_memory_update_node(
    state: SessionState, config: RunnableConfig
) -> dict[str, object]:
    persona_facts = state["persona_facts"]
    if not persona_facts:
        return {}

    persona_service: PersonaService = config["configurable"]["persona_service"]
    await persona_service.remember(
        state["user_id"], state["scenario_id"], persona_facts
    )

    return {}
