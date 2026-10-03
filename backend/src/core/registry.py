from analysis.models import SessionAnalysis
from auth.models import UserSession
from core.base_model import Base
from persona.models import PersonaMemory
from practice.models import LearningSession
from users.models import User
from weaknesses.models import WeaknessRecord

__all__ = [
    "Base",
    "LearningSession",
    "PersonaMemory",
    "SessionAnalysis",
    "User",
    "UserSession",
    "WeaknessRecord",
    "is_externally_managed_table",
]

metadata = Base.metadata

_EXTERNALLY_MANAGED_TABLE_PREFIXES = ("checkpoint",)


def is_externally_managed_table(name: str | None) -> bool:
    return name is not None and name.startswith(_EXTERNALLY_MANAGED_TABLE_PREFIXES)
