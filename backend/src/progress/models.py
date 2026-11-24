import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base


class SessionProgress(Base):
    __tablename__ = "session_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_sessions.id", ondelete="CASCADE"),
        unique=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    grammar_issue_count: Mapped[int] = mapped_column(Integer)
    vocabulary_issue_count: Mapped[int] = mapped_column(Integer)
    goals_achieved: Mapped[int] = mapped_column(Integer)
    goals_total: Mapped[int] = mapped_column(Integer)
    learner_word_count: Mapped[int] = mapped_column(Integer)
    total_word_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
