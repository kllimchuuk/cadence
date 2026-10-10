import json

from langgraph.runtime import Runtime

from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.service import AnalysisService
from llm.client import ChatMessage, MessageRole
from orchestration.context import SessionRuntimeContext
from orchestration.schemas import SessionAnalysisResult
from orchestration.state import SessionState
from practice.repository import LearningSessionRepositoryImpl
from scenarios.config import Scenario, get_scenario


def _build_system_instruction(scenario: Scenario) -> str:
    goals = "; ".join(scenario.goal_checklist)
    return (
        "Analyse the practice-conversation transcript the user sends as a JSON "
        'list of turns. Judge only the turns whose role is "user" — those are '
        "the learner's — for grammar, vocabulary, fluency and task completion. "
        f"Score task completion against this checklist: {goals}.\n"
        "Report 1-3 focus points, one observation per tracked skill (error or "
        "clean use), and any new facts about the user worth remembering for "
        "next time."
    )


def _transcript_messages(transcript: list[dict[str, str]]) -> list[ChatMessage]:
    return [ChatMessage(MessageRole.USER, json.dumps(transcript, ensure_ascii=False))]


async def session_analysis_node(
    state: SessionState, *, runtime: Runtime[SessionRuntimeContext]
) -> dict[str, object]:
    scenario = get_scenario(state["scenario_id"])
    result = await runtime.context.session_analysis_llm.generate_structured(
        _build_system_instruction(scenario),
        _transcript_messages(state["transcript"]),
        SessionAnalysisResult,
    )

    async with runtime.context.session_factory() as session:
        analysis_service = AnalysisService(
            SessionAnalysisRepositoryImpl(session),
            LearningSessionRepositoryImpl(session),
        )
        await analysis_service.create_analysis(
            session_id=state["session_id"],
            user_id=state["user_id"],
            grammar_findings=result.grammar_findings,
            vocabulary_findings=result.vocabulary_findings,
            fluency_findings=result.fluency_findings,
            task_completion=result.task_completion,
            focus_points=result.focus_points,
        )
        await session.commit()

    return {
        "skill_observations": [
            observation.model_dump() for observation in result.skill_observations
        ],
        "persona_facts": result.new_facts,
        "focus_points": result.focus_points,
    }
