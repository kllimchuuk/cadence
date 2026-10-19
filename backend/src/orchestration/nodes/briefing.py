from langgraph.runtime import Runtime

from orchestration.context import ConversationRuntimeContext
from orchestration.prompts import (
    build_persona_system_prompt,
    build_scenario_content_query,
    opening_messages,
)
from orchestration.state import ConversationState
from orchestration.streaming import stream_reply
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from rag.repository import ContentChunkRepositoryImpl
from rag.service import ContentRetrievalService
from scenarios.config import get_scenario

SCENARIO_CONTENT_LIMIT = 5


async def briefing_node(
    state: ConversationState, *, runtime: Runtime[ConversationRuntimeContext]
) -> dict[str, object]:
    scenario = get_scenario(state["scenario_id"])

    async with runtime.context.session_factory() as session:
        persona_service = PersonaService(PersonaMemoryRepositoryImpl(session))
        persona_memory = await persona_service.get_memory(
            state["user_id"], state["scenario_id"]
        )
        reference_content = await ContentRetrievalService(
            ContentChunkRepositoryImpl(session), runtime.context.embedder
        ).search_scenario_content(
            scenario.id,
            build_scenario_content_query(scenario, persona_memory),
            SCENARIO_CONTENT_LIMIT,
        )

    system_prompt = build_persona_system_prompt(
        scenario, persona_memory, reference_content
    )
    opening_line = await stream_reply(
        runtime.context.briefing_llm,
        system_prompt,
        opening_messages(),
        runtime.stream_writer,
    )
    return {
        "system_prompt": system_prompt,
        "transcript": [{"role": "assistant", "content": opening_line}],
    }
