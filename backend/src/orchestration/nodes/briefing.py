import asyncio
import logging

from langgraph.runtime import Runtime

from llm.exceptions import LLMUnavailableError
from orchestration.context import ConversationRuntimeContext
from orchestration.prompts import (
    build_persona_system_prompt,
    build_scenario_content_query,
    opening_messages,
)
from orchestration.state import ConversationState
from orchestration.streaming import stream_reply
from persona.models import PersonaMemory
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from rag.entries import RetrievedChunk
from rag.repository import ContentChunkRepositoryImpl
from rag.service import ContentRetrievalService
from scenarios.config import Scenario, get_scenario

SCENARIO_CONTENT_LIMIT = 10
SCENARIO_CONTENT_TIMEOUT_SECONDS = 5

logger = logging.getLogger(__name__)


async def _load_persona_memory(
    runtime: Runtime[ConversationRuntimeContext], state: ConversationState
) -> PersonaMemory | None:
    async with runtime.context.session_factory() as session:
        return await PersonaService(PersonaMemoryRepositoryImpl(session)).get_memory(
            state["user_id"], state["scenario_id"]
        )


async def _retrieve_reference_content(
    runtime: Runtime[ConversationRuntimeContext],
    scenario: Scenario,
    persona_memory: PersonaMemory | None,
) -> list[RetrievedChunk]:
    try:
        async with asyncio.timeout(SCENARIO_CONTENT_TIMEOUT_SECONDS):
            async with runtime.context.session_factory() as session:
                return await ContentRetrievalService(
                    ContentChunkRepositoryImpl(session), runtime.context.embedder
                ).search_scenario_content(
                    scenario.id,
                    build_scenario_content_query(scenario, persona_memory),
                    SCENARIO_CONTENT_LIMIT,
                )
    except (LLMUnavailableError, TimeoutError):
        logger.warning(
            "Scenario content unavailable; briefing %s without it",
            scenario.id,
            exc_info=True,
        )
        return []


async def briefing_node(
    state: ConversationState, *, runtime: Runtime[ConversationRuntimeContext]
) -> dict[str, object]:
    scenario = get_scenario(state["scenario_id"])
    persona_memory = await _load_persona_memory(runtime, state)
    reference_content = await _retrieve_reference_content(
        runtime, scenario, persona_memory
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
