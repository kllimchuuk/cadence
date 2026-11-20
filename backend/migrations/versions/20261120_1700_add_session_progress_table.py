"""add the session progress table

Revision ID: 5d8e2a41b7c9
Revises: 7b1c4d9e2a60
Create Date: 2026-11-20 17:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5d8e2a41b7c9"
down_revision: str | None = "7b1c4d9e2a60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_progress",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("grammar_issue_count", sa.Integer(), nullable=False),
        sa.Column("vocabulary_issue_count", sa.Integer(), nullable=False),
        sa.Column("goals_achieved", sa.Integer(), nullable=False),
        sa.Column("goals_total", sa.Integer(), nullable=False),
        sa.Column("learner_word_count", sa.Integer(), nullable=False),
        sa.Column("total_word_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["learning_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(
        op.f("ix_session_progress_user_id"),
        "session_progress",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("session_progress")
