from langgraph.runtime import Runtime
from langgraph.types import interrupt

from orchestration.context import SessionRuntimeContext
from orchestration.prompts import (
    build_persona_system_prompt,
    conversation_messages,
)
from orchestration.state import SessionState
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from scenarios.config import get_scenario

MAX_CONVERSATION_TURNS = 12
END_SESSION_REQUEST = {"type": "end_session"}


async def conversing_node(
    state: SessionState, *, runtime: Runtime[SessionRuntimeContext]
) -> dict[str, object]:
    user_turn = interrupt({"awaiting": "user_turn"})
    if user_turn == END_SESSION_REQUEST:
        return {"should_exit": True}

    scenario = get_scenario(state["scenario_id"])

    async with runtime.context.session_factory() as session:
        persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
        persona_memory = await persona_service.get_memory(
            state["user_id"], state["scenario_id"]
        )

    system_prompt = build_persona_system_prompt(scenario, persona_memory)
    assistant_reply = await runtime.context.conversing_llm.generate(
        system_prompt, conversation_messages(state["transcript"], user_turn)
    )

    turn_count = state["turn_count"] + 1
    return {
        "transcript": [
            {"role": "user", "content": user_turn},
            {"role": "assistant", "content": assistant_reply},
        ],
        "turn_count": turn_count,
        "should_exit": turn_count >= MAX_CONVERSATION_TURNS,
    }
