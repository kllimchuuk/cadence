from langchain_core.runnables import RunnableConfig

from analysis.service import AnalysisService
from llm.client import LLMClient
from orchestration.schemas import SessionAnalysisResult
from orchestration.state import SessionState


def _build_prompt(transcript: list[dict[str, str]]) -> str:
    history = "\n".join(f'{entry["role"]}: {entry["content"]}' for entry in transcript)
    return (
        "Analyse this practice-conversation transcript for grammar, vocabulary, "
        "fluency and task completion. Report 1-3 focus points, one observation "
        "per tracked skill (error or clean use), and any new facts about the "
        f"user worth remembering for next time.\n\n{history}"
    )


async def session_analysis_node(
    state: SessionState, config: RunnableConfig
) -> dict[str, object]:
    llm_client: LLMClient = config["configurable"]["session_analysis_llm"]
    analysis_service: AnalysisService = config["configurable"]["analysis_service"]

    prompt = _build_prompt(state["transcript"])
    result = await llm_client.generate_structured(prompt, SessionAnalysisResult)

    await analysis_service.create_analysis(
        session_id=state["session_id"],
        user_id=state["user_id"],
        grammar_findings=result.grammar_findings,
        vocabulary_findings=result.vocabulary_findings,
        fluency_findings=result.fluency_findings,
        task_completion=result.task_completion,
        focus_points=result.focus_points,
    )

    return {
        "skill_observations": [
            observation.model_dump() for observation in result.skill_observations
        ],
        "persona_facts": result.new_facts,
    }
