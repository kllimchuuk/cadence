"""enable pgvector and add the content chunks table

Revision ID: 7b1c4d9e2a60
Revises: e407f34375e5
Create Date: 2026-10-19 17:00:00.000000+00:00

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7b1c4d9e2a60"
down_revision: str | None = "e407f34375e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "content_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corpus", sa.String(length=30), nullable=False),
        sa.Column("scenario_id", sa.String(length=100), nullable=True),
        sa.Column("skill_key", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=768), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "corpus IN ('scenario_content', 'grammar_reference')",
            name="ck_content_chunks_corpus",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
    )
    op.create_index(
        "ix_content_chunks_corpus_scenario_id",
        "content_chunks",
        ["corpus", "scenario_id"],
    )
    op.create_index("ix_content_chunks_skill_key", "content_chunks", ["skill_key"])
    op.create_index(
        "ix_content_chunks_embedding",
        "content_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("content_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
