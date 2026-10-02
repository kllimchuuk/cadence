import uuid
from typing import Annotated

from fastapi import Depends

from persona.exceptions import InvalidFactError
from persona.models import PersonaMemory
from persona.repository import PersonaMemoryRepository, get_persona_repository


class PersonaService:
    def __init__(self, repository: PersonaMemoryRepository) -> None:
        self._repository = repository

    async def get_memory(
        self, user_id: uuid.UUID, scenario_id: str
    ) -> PersonaMemory | None:
        return await self._repository.get_by_user_and_scenario(user_id, scenario_id)

    async def remember(
        self, user_id: uuid.UUID, scenario_id: str, new_facts: list[str]
    ) -> PersonaMemory:
        self._require_valid_facts(new_facts)

        record = await self._repository.get_by_user_and_scenario(user_id, scenario_id)
        if record is None:
            return await self._repository.create(user_id, scenario_id, new_facts)

        merged = record.facts + [fact for fact in new_facts if fact not in record.facts]
        return await self._repository.update_facts(record, merged)

    @staticmethod
    def _require_valid_facts(facts: list[str]) -> None:
        if any(not fact.strip() for fact in facts):
            raise InvalidFactError()


def get_persona_service(
    repository: Annotated[PersonaMemoryRepository, Depends(get_persona_repository)],
) -> PersonaService:
    return PersonaService(repository)
