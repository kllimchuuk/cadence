from langgraph.runtime import Runtime

from orchestration.context import SessionRuntimeContext
from orchestration.prompts import build_persona_system_prompt
from orchestration.state import SessionState
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from scenarios.config import get_scenario

_PLACEHOLDER_USER_TURN = "Hello!"
_MAX_PLACEHOLDER_TURNS = 2


def _build_prompt(
    system_prompt: str, transcript: list[dict[str, str]], user_turn: str
) -> str:
    history = "\n".join(f'{entry["role"]}: {entry["content"]}' for entry in transcript)
    return f"{system_prompt}\n\n{history}\nuser: {user_turn}\nassistant:"


async def conversing_node(
    state: SessionState, *, runtime: Runtime[SessionRuntimeContext]
) -> dict[str, object]:
    scenario = get_scenario(state["scenario_id"])

    async with runtime.context.session_factory() as session:
        persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
        persona_memory = await persona_service.get_memory(
            state["user_id"], state["scenario_id"]
        )

    system_prompt = build_persona_system_prompt(scenario, persona_memory)
    prompt = _build_prompt(system_prompt, state["transcript"], _PLACEHOLDER_USER_TURN)
    assistant_reply = await runtime.context.conversing_llm.generate(prompt)

    turn_count = state["turn_count"] + 1
    return {
        "transcript": [
            {"role": "user", "content": _PLACEHOLDER_USER_TURN},
            {"role": "assistant", "content": assistant_reply},
        ],
        "turn_count": turn_count,
        "should_exit": turn_count >= _MAX_PLACEHOLDER_TURNS,
    }
