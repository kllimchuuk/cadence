import uuid
from typing import Literal

from pydantic import BaseModel, Field

MAX_USER_TURN_LENGTH = 4000


class UserMessage(BaseModel):
    type: Literal["user_message"]
    content: str = Field(min_length=1, max_length=MAX_USER_TURN_LENGTH)


class SessionStarted(BaseModel):
    type: Literal["session_started"] = "session_started"
    session_id: uuid.UUID


class AssistantMessage(BaseModel):
    type: Literal["assistant_message"] = "assistant_message"
    content: str


class SessionEnded(BaseModel):
    type: Literal["session_ended"] = "session_ended"
    focus_points: list[str]
