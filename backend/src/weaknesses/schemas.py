import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from weaknesses.models import WeaknessCategory, WeaknessState


class WeaknessPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: WeaknessCategory
    skill_key: str
    state: WeaknessState
    clean_streak: int
    last_session_id: uuid.UUID | None
    updated_at: datetime
