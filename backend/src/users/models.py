import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from core.base_model import Base

DEFAULT_UI_LANGUAGE = "uk"
DEFAULT_TIMEZONE = "Europe/Kyiv"


def normalize_email(value: str) -> str:
    return value.strip().lower()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_users_email_is_lowercase"),
        CheckConstraint(
            "hashed_password IS NOT NULL OR google_sub IS NOT NULL",
            name="ck_users_has_password_or_google_sub",
        ),
        Index("ix_users_nickname_lower", text("lower(nickname)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    nickname: Mapped[str] = mapped_column(String(50))
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    ui_language: Mapped[str] = mapped_column(
        String(5), default=DEFAULT_UI_LANGUAGE, server_default=DEFAULT_UI_LANGUAGE
    )
    timezone: Mapped[str] = mapped_column(
        String(64), default=DEFAULT_TIMEZONE, server_default=DEFAULT_TIMEZONE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return normalize_email(value)
