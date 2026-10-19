from langgraph.runtime import Runtime

from orchestration.context import AnalysisRuntimeContext
from orchestration.state import AnalysisState
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService


async def persona_memory_update_node(
    state: AnalysisState, *, runtime: Runtime[AnalysisRuntimeContext]
) -> dict[str, object]:
    persona_facts = state["persona_facts"]
    if not persona_facts:
        return {}

    async with runtime.context.session_factory() as session:
        persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
        await persona_service.remember(
            state["user_id"], state["scenario_id"], persona_facts
        )
        await session.commit()

    return {}
