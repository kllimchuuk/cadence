"""add user sessions table, nickname and google auth on users

Revision ID: 35526200c083
Revises: 46cf75d59cad
Create Date: 2026-09-07 18:33:06.356405+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "35526200c083"
down_revision: str | None = "46cf75d59cad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False
    )

    op.add_column(
        "users",
        sa.Column(
            "first_name", sa.String(length=100), nullable=False, server_default=""
        ),
    )
    op.alter_column("users", "first_name", server_default=None)
    op.add_column(
        "users",
        sa.Column(
            "last_name", sa.String(length=100), nullable=False, server_default=""
        ),
    )
    op.alter_column("users", "last_name", server_default=None)
    op.add_column("users", sa.Column("nickname", sa.String(length=50), nullable=True))
    op.execute("UPDATE users SET nickname = 'user-' || id::text")
    op.alter_column("users", "nickname", nullable=False)
    op.add_column(
        "users", sa.Column("google_sub", sa.String(length=255), nullable=True)
    )
    op.alter_column("users", "hashed_password", nullable=True)
    op.create_check_constraint(
        "ck_users_has_password_or_google_sub",
        "users",
        "hashed_password IS NOT NULL OR google_sub IS NOT NULL",
    )
    op.create_index(
        "ix_users_nickname_lower", "users", [sa.text("lower(nickname)")], unique=True
    )
    op.create_index(op.f("ix_users_google_sub"), "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_google_sub"), table_name="users")
    op.drop_index("ix_users_nickname_lower", table_name="users")
    op.drop_constraint("ck_users_has_password_or_google_sub", "users", type_="check")
    op.execute("UPDATE users SET hashed_password = '!' WHERE hashed_password IS NULL")
    op.alter_column("users", "hashed_password", nullable=False)
    op.drop_column("users", "google_sub")
    op.drop_column("users", "nickname")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")

    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
