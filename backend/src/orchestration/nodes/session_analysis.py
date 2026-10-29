import json
import logging
import uuid
from collections.abc import Collection, Sequence

from langgraph.runtime import Runtime

from analysis.evidence import find_unquoted_evidence, keep_quoted, learner_turns
from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.schemas import GrammarTriage, SessionAnalysisResult
from analysis.service import AnalysisService
from llm.client import ChatMessage, MessageRole
from orchestration.context import AnalysisRuntimeContext
from orchestration.prompts import (
    build_analysis_system_instruction,
    build_evidence_correction,
    build_grammar_triage_instruction,
)
from orchestration.state import AnalysisState
from practice.repository import LearningSessionRepositoryImpl
from rag.models import ContentChunk
from rag.repository import ContentChunkRepositoryImpl
from rag.service import GrammarReferenceService
from scenarios.config import get_scenario
from weaknesses.models import WeaknessRecord
from weaknesses.repository import WeaknessRecordRepositoryImpl
from weaknesses.service import WeaknessService

logger = logging.getLogger(__name__)


def _transcript_messages(transcript: list[dict[str, str]]) -> list[ChatMessage]:
    return [ChatMessage(MessageRole.USER, json.dumps(transcript, ensure_ascii=False))]


async def _load_active_weaknesses(
    runtime: Runtime[AnalysisRuntimeContext], user_id: uuid.UUID
) -> list[WeaknessRecord]:
    async with runtime.context.session_factory() as session:
        return await WeaknessService(
            WeaknessRecordRepositoryImpl(session),
            LearningSessionRepositoryImpl(session),
        ).get_active_weaknesses(user_id)


async def _load_grammar_rules(
    runtime: Runtime[AnalysisRuntimeContext], skill_keys: Collection[str]
) -> list[ContentChunk]:
    async with runtime.context.session_factory() as session:
        return await GrammarReferenceService(
            ContentChunkRepositoryImpl(session)
        ).get_rules(skill_keys)


async def _retrieve_grammar_reference(
    runtime: Runtime[AnalysisRuntimeContext],
    messages: Sequence[ChatMessage],
    active_weaknesses: Sequence[WeaknessRecord],
) -> list[ContentChunk]:
    triage = await runtime.context.session_analysis_llm.generate_structured(
        build_grammar_triage_instruction(active_weaknesses),
        messages,
        GrammarTriage,
    )
    skill_keys = {key.value for key in triage.skill_keys}
    skill_keys.update(weakness.skill_key for weakness in active_weaknesses)
    return await _load_grammar_rules(runtime, skill_keys)


async def _generate_quoted_analysis(
    runtime: Runtime[AnalysisRuntimeContext],
    system_instruction: str,
    messages: Sequence[ChatMessage],
    state: AnalysisState,
) -> SessionAnalysisResult:
    llm = runtime.context.session_analysis_llm
    turns = learner_turns(state["transcript"])
    result = await llm.generate_structured(
        system_instruction, messages, SessionAnalysisResult
    )
    unquoted = find_unquoted_evidence(result, turns)
    if unquoted:
        logger.warning(
            "Session %s analysis quoted words the learner never said: %s",
            state["session_id"],
            unquoted,
        )
        result = await llm.generate_structured(
            system_instruction,
            [
                *messages,
                ChatMessage(MessageRole.ASSISTANT, result.model_dump_json()),
                ChatMessage(MessageRole.USER, build_evidence_correction(unquoted)),
            ],
            SessionAnalysisResult,
        )
        unquoted = find_unquoted_evidence(result, turns)
        if unquoted:
            logger.warning(
                "Session %s: dropping analysis items with invented evidence: %s",
                state["session_id"],
                unquoted,
            )
    return keep_quoted(result, turns)


async def _save_analysis(
    runtime: Runtime[AnalysisRuntimeContext],
    state: AnalysisState,
    result: SessionAnalysisResult,
) -> None:
    async with runtime.context.session_factory() as session:
        analysis_service = AnalysisService(
            SessionAnalysisRepositoryImpl(session),
            LearningSessionRepositoryImpl(session),
        )
        await analysis_service.create_analysis(
            state["session_id"], state["user_id"], result
        )
        await session.commit()


async def session_analysis_node(
    state: AnalysisState, *, runtime: Runtime[AnalysisRuntimeContext]
) -> dict[str, object]:
    scenario = get_scenario(state["scenario_id"])
    messages = _transcript_messages(state["transcript"])
    active_weaknesses = await _load_active_weaknesses(runtime, state["user_id"])
    grammar_reference = await _retrieve_grammar_reference(
        runtime, messages, active_weaknesses
    )

    result = await _generate_quoted_analysis(
        runtime,
        build_analysis_system_instruction(
            scenario, grammar_reference, active_weaknesses
        ),
        messages,
        state,
    )
    await _save_analysis(runtime, state, result)

    return {
        "skill_observations": [
            observation.model_dump() for observation in result.skill_observations
        ],
        "persona_facts": [persona_fact.fact for persona_fact in result.new_facts],
        "focus_points": result.focus_points,
    }
