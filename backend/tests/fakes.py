import hashlib
import math
import re
import sys
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

from analysis.schemas import (
    FluencyAssessment,
    PersonaFact,
    SessionAnalysisResult,
    SkillObservation,
    TaskCompletion,
)
from llm.client import ChatMessage
from llm.exceptions import LLMResponseError
from rag.embeddings import EMBEDDING_DIMENSIONS, EmbeddingDocument


def reply_deltas(reply: str) -> list[str]:
    return re.findall(r"\S+\s*", reply)


@dataclass(frozen=True)
class LLMRequest:
    system_instruction: str
    messages: tuple[ChatMessage, ...]


def analysis_result(
    skill_observations: list[SkillObservation] | None = None,
    new_facts: list[str] | None = None,
) -> SessionAnalysisResult:
    return SessionAnalysisResult(
        grammar_findings=[],
        vocabulary_findings=[],
        fluency_findings=FluencyAssessment(summary="Steady, with a few pauses."),
        task_completion=TaskCompletion(goals=[]),
        focus_points=["Practice past-tense verbs"],
        skill_observations=skill_observations or [],
        new_facts=[PersonaFact(fact=fact, evidence=fact) for fact in new_facts or []],
    )


class FakeLLMClient:
    def __init__(
        self,
        reply: str = "Tell me more.",
        analysis: SessionAnalysisResult | None = None,
    ) -> None:
        self._reply = reply
        self._analysis = analysis or analysis_result()
        self.requests: list[LLMRequest] = []

    async def stream(
        self, system_instruction: str, messages: Sequence[ChatMessage]
    ) -> AsyncIterator[str]:
        self.requests.append(LLMRequest(system_instruction, tuple(messages)))
        for delta in reply_deltas(self._reply):
            yield delta

    async def generate_structured(
        self,
        system_instruction: str,
        messages: Sequence[ChatMessage],
        schema: type,
    ) -> SessionAnalysisResult:
        self.requests.append(LLMRequest(system_instruction, tuple(messages)))
        return self._analysis


class FlakyLLMClient(FakeLLMClient):
    def __init__(
        self,
        reply: str,
        fail_times: int,
        error: Exception = LLMResponseError("transient failure"),
    ) -> None:
        super().__init__(reply)
        self._fail_times = fail_times
        self._error = error
        self.call_count = 0

    async def stream(
        self, system_instruction: str, messages: Sequence[ChatMessage]
    ) -> AsyncIterator[str]:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise self._error
        async for delta in super().stream(system_instruction, messages):
            yield delta


class FailingLLMClient(FlakyLLMClient):
    def __init__(self) -> None:
        super().__init__(
            "", fail_times=sys.maxsize, error=RuntimeError("the model is unavailable")
        )


class FailingAnalysisLLMClient(FakeLLMClient):
    async def generate_structured(
        self,
        system_instruction: str,
        messages: Sequence[ChatMessage],
        schema: type,
    ) -> SessionAnalysisResult:
        raise RuntimeError("the analysis model is unavailable")


class FakeLLMClientFactory:
    def __init__(self, client: FakeLLMClient) -> None:
        self._client = client

    def create(self, _model: str) -> FakeLLMClient:
        return self._client

    def create_embedding_client(self, _model: str) -> "FakeEmbeddingClient":
        return FakeEmbeddingClient()


def fake_embedding(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for word in re.findall(r"[a-z']+", text.lower()):
        digest = hashlib.sha256(word.encode()).digest()
        vector[int.from_bytes(digest[:4]) % EMBEDDING_DIMENSIONS] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.document_calls: list[tuple[EmbeddingDocument, ...]] = []
        self.queries: list[str] = []

    async def embed_documents(
        self, documents: Sequence[EmbeddingDocument]
    ) -> list[list[float]]:
        self.document_calls.append(tuple(documents))
        return [fake_embedding(f"{item.title or ''} {item.text}") for item in documents]

    async def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return fake_embedding(text)
