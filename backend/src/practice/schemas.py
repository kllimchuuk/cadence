import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

MAX_USER_TURN_LENGTH = 4000


class UserMessage(BaseModel):
    type: Literal["user_message"]
    content: str = Field(min_length=1, max_length=MAX_USER_TURN_LENGTH)


class EndSession(BaseModel):
    type: Literal["end_session"]


ClientMessage = Annotated[UserMessage | EndSession, Field(discriminator="type")]
CLIENT_MESSAGE_ADAPTER = TypeAdapter(ClientMessage)


class SessionStarted(BaseModel):
    type: Literal["session_started"] = "session_started"
    session_id: uuid.UUID


class AssistantMessage(BaseModel):
    type: Literal["assistant_message"] = "assistant_message"
    content: str


class InvalidMessage(BaseModel):
    type: Literal["invalid_message"] = "invalid_message"


class SessionEnded(BaseModel):
    type: Literal["session_ended"] = "session_ended"
    focus_points: list[str]
