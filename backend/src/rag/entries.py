import hashlib
import json
from dataclasses import dataclass

from rag.models import Corpus


@dataclass(frozen=True)
class ContentEntry:
    corpus: Corpus
    title: str
    content: str
    scenario_id: str | None = None
    skill_key: str | None = None

    @property
    def content_hash(self) -> str:
        identity = [
            self.corpus,
            self.scenario_id,
            self.skill_key,
            self.title,
            self.content,
        ]
        return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


@dataclass(frozen=True)
class RetrievedChunk:
    title: str
    content: str
    skill_key: str | None
    distance: float


@dataclass(frozen=True)
class EmbeddedEntry:
    entry: ContentEntry
    embedding: list[float]
    embedding_model: str
