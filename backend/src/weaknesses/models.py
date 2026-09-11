import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base
from core.sql import enum_check


class WeaknessCategory(StrEnum):
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    FLUENCY = "fluency"
    TASK_COMPLETION = "task_completion"


class WeaknessState(StrEnum):
    NEW = "new"
    ACTIVE = "active"
    PROBATION = "probation"
    MASTERED = "mastered"


class WeaknessRecord(Base):
    __tablename__ = "weakness_records"
    __table_args__ = (
        enum_check("category", "ck_weakness_records_category", WeaknessCategory),
        enum_check("state", "ck_weakness_records_state", WeaknessState),
        UniqueConstraint(
            "user_id", "category", "skill_key", name="uq_weakness_records_user_skill"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(20))
    skill_key: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(
        String(20), default=WeaknessState.NEW, server_default=WeaknessState.NEW
    )
    clean_streak: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
