import json

from langgraph.runtime import Runtime

from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.schemas import SessionAnalysisResult
from analysis.service import AnalysisService
from llm.client import ChatMessage, MessageRole
from orchestration.context import AnalysisRuntimeContext
from orchestration.prompts import (
    build_analysis_system_instruction,
    build_grammar_reference_query,
)
from orchestration.state import AnalysisState
from practice.repository import LearningSessionRepositoryImpl
from rag.repository import ContentChunkRepositoryImpl
from rag.service import ContentRetrievalService
from scenarios.config import get_scenario
from weaknesses.repository import WeaknessRecordRepositoryImpl
from weaknesses.service import WeaknessService

GRAMMAR_REFERENCE_LIMIT = 6


def _transcript_messages(transcript: list[dict[str, str]]) -> list[ChatMessage]:
    return [ChatMessage(MessageRole.USER, json.dumps(transcript, ensure_ascii=False))]


async def session_analysis_node(
    state: AnalysisState, *, runtime: Runtime[AnalysisRuntimeContext]
) -> dict[str, object]:
    scenario = get_scenario(state["scenario_id"])

    async with runtime.context.session_factory() as session:
        grammar_reference = await ContentRetrievalService(
            ContentChunkRepositoryImpl(session), runtime.context.embedder
        ).search_grammar_reference(
            build_grammar_reference_query(state["transcript"]),
            GRAMMAR_REFERENCE_LIMIT,
        )
        active_weaknesses = await WeaknessService(
            WeaknessRecordRepositoryImpl(session),
            LearningSessionRepositoryImpl(session),
        ).get_active_weaknesses(state["user_id"])

    result = await runtime.context.session_analysis_llm.generate_structured(
        build_analysis_system_instruction(
            scenario, grammar_reference, active_weaknesses
        ),
        _transcript_messages(state["transcript"]),
        SessionAnalysisResult,
    )

    async with runtime.context.session_factory() as session:
        analysis_service = AnalysisService(
            SessionAnalysisRepositoryImpl(session),
            LearningSessionRepositoryImpl(session),
        )
        await analysis_service.create_analysis(
            state["session_id"], state["user_id"], result
        )
        await session.commit()

    return {
        "skill_observations": [
            observation.model_dump() for observation in result.skill_observations
        ],
        "persona_facts": [persona_fact.fact for persona_fact in result.new_facts],
        "focus_points": result.focus_points,
    }
