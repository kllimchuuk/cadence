import operator
import uuid
from typing import Annotated, TypedDict


class SessionState(TypedDict):
    session_id: uuid.UUID
    user_id: uuid.UUID
    scenario_id: str
    transcript: Annotated[list[dict[str, str]], operator.add]
    turn_count: int
    should_exit: bool
    skill_observations: list[dict[str, str]]
    persona_facts: list[str]
