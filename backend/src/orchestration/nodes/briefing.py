from langgraph.runtime import Runtime

from orchestration.context import SessionRuntimeContext
from orchestration.prompts import build_persona_system_prompt, opening_messages
from orchestration.state import SessionState
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from scenarios.config import get_scenario


async def briefing_node(
    state: SessionState, *, runtime: Runtime[SessionRuntimeContext]
) -> dict[str, object]:
    scenario = get_scenario(state["scenario_id"])

    async with runtime.context.session_factory() as session:
        persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
        persona_memory = await persona_service.get_memory(
            state["user_id"], state["scenario_id"]
        )

    system_prompt = build_persona_system_prompt(scenario, persona_memory)
    opening_line = await runtime.context.briefing_llm.generate(
        system_prompt, opening_messages()
    )
    return {
        "system_prompt": system_prompt,
        "transcript": [{"role": "assistant", "content": opening_line}],
    }
