from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str


class LLMClient(Protocol):
    async def generate(
        self, system_instruction: str, messages: Sequence[ChatMessage]
    ) -> str:
        raise NotImplementedError()

    async def generate_structured(
        self,
        system_instruction: str,
        messages: Sequence[ChatMessage],
        schema: type[SchemaT],
    ) -> SchemaT:
        raise NotImplementedError()
