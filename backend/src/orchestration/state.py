import uuid
from typing import TypedDict


class SessionState(TypedDict):
    session_id: uuid.UUID
    user_id: uuid.UUID
    scenario_id: str
    transcript: list[dict[str, str]]
    turn_count: int
