import operator
import uuid
from typing import Annotated, TypedDict


class SessionState(TypedDict):
    session_id: uuid.UUID
    user_id: uuid.UUID
    scenario_id: str
    system_prompt: str
    transcript: Annotated[list[dict[str, str]], operator.add]
    turn_count: int
    should_exit: bool
    skill_observations: list[dict[str, str]]
    persona_facts: list[str]
    focus_points: list[str]


def initial_session_state(
    session_id: uuid.UUID, user_id: uuid.UUID, scenario_id: str
) -> SessionState:
    return SessionState(
        session_id=session_id,
        user_id=user_id,
        scenario_id=scenario_id,
        system_prompt="",
        transcript=[],
        turn_count=0,
        should_exit=False,
        skill_observations=[],
        persona_facts=[],
        focus_points=[],
    )
