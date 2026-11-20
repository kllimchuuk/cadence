import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base

_WORDS_PER_RATE_UNIT = 100


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

    @property
    def grammar_issue_rate(self) -> float:
        return self._per_hundred_learner_words(self.grammar_issue_count)

    @property
    def vocabulary_issue_rate(self) -> float:
        return self._per_hundred_learner_words(self.vocabulary_issue_count)

    @property
    def goal_completion_rate(self) -> float:
        if not self.goals_total:
            return 0.0
        return self.goals_achieved / self.goals_total

    @property
    def learner_word_share(self) -> float:
        if not self.total_word_count:
            return 0.0
        return self.learner_word_count / self.total_word_count

    def _per_hundred_learner_words(self, count: int) -> float:
        if not self.learner_word_count:
            return 0.0
        return count * _WORDS_PER_RATE_UNIT / self.learner_word_count
