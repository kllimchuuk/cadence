from typing import Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMClient(Protocol):
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError()

    async def generate_structured(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        raise NotImplementedError()
