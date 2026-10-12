import operator
import uuid
from typing import Annotated, TypedDict


class ConversationState(TypedDict):
    session_id: uuid.UUID
    user_id: uuid.UUID
    scenario_id: str
    system_prompt: str
    transcript: Annotated[list[dict[str, str]], operator.add]
    turn_count: int
    should_exit: bool


class AnalysisState(TypedDict):
    session_id: uuid.UUID
    user_id: uuid.UUID
    scenario_id: str
    transcript: list[dict[str, str]]
    skill_observations: list[dict[str, str]]
    persona_facts: list[str]
    focus_points: list[str]


def initial_conversation_state(
    session_id: uuid.UUID, user_id: uuid.UUID, scenario_id: str
) -> ConversationState:
    return ConversationState(
        session_id=session_id,
        user_id=user_id,
        scenario_id=scenario_id,
        system_prompt="",
        transcript=[],
        turn_count=0,
        should_exit=False,
    )


def initial_analysis_state(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    scenario_id: str,
    transcript: list[dict[str, str]],
) -> AnalysisState:
    return AnalysisState(
        session_id=session_id,
        user_id=user_id,
        scenario_id=scenario_id,
        transcript=transcript,
        skill_observations=[],
        persona_facts=[],
        focus_points=[],
    )
