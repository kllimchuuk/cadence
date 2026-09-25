from langgraph.runtime import Runtime

from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.service import AnalysisService
from orchestration.context import SessionRuntimeContext
from orchestration.schemas import SessionAnalysisResult
from orchestration.state import SessionState
from practice.repository import LearningSessionRepositoryImpl
from scenarios.config import Scenario, get_scenario


def _build_prompt(scenario: Scenario, transcript: list[dict[str, str]]) -> str:
    history = "\n".join(f'{entry["role"]}: {entry["content"]}' for entry in transcript)
    goals = "; ".join(scenario.goal_checklist)
    return (
        "Analyse this practice-conversation transcript for grammar, vocabulary, "
        "fluency and task completion. Score task completion against this "
        f"checklist: {goals}.\n"
        "Report 1-3 focus points, one observation per tracked skill (error or "
        "clean use), and any new facts about the user worth remembering for "
        f"next time.\n\n{history}"
    )


async def session_analysis_node(
    state: SessionState, *, runtime: Runtime[SessionRuntimeContext]
) -> dict[str, object]:
    scenario = get_scenario(state["scenario_id"])
    prompt = _build_prompt(scenario, state["transcript"])
    result = await runtime.context.session_analysis_llm.generate_structured(
        prompt, SessionAnalysisResult
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
    }
