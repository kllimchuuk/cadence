import uuid
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base
from core.sql import enum_check
from rag.embeddings import EMBEDDING_DIMENSIONS


class Corpus(StrEnum):
    SCENARIO_CONTENT = "scenario_content"
    GRAMMAR_REFERENCE = "grammar_reference"


class ContentChunk(Base):
    __tablename__ = "content_chunks"
    __table_args__ = (
        enum_check("corpus", "ck_content_chunks_corpus", Corpus),
        Index(
            "ix_content_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    corpus: Mapped[str] = mapped_column(String(30), index=True)
    scenario_id: Mapped[str | None] = mapped_column(String(100), index=True)
    skill_key: Mapped[str | None] = mapped_column(String(100), index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    embedding_model: Mapped[str] = mapped_column(String(100))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
