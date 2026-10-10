"""add skill observations and new facts to session analyses

Revision ID: e407f34375e5
Revises: cd5634f0fa16
Create Date: 2026-10-10 17:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e407f34375e5"
down_revision: str | None = "cd5634f0fa16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_ANALYSIS_COLUMNS = ("skill_observations", "new_facts")


def upgrade() -> None:
    for column in _NEW_ANALYSIS_COLUMNS:
        op.add_column(
            "session_analyses",
            sa.Column(
                column,
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )
        op.alter_column("session_analyses", column, server_default=None)


def downgrade() -> None:
    for column in reversed(_NEW_ANALYSIS_COLUMNS):
        op.drop_column("session_analyses", column)
