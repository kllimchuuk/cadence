from collections.abc import Sequence
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

    async def generate(
        self, system_instruction: str, messages: Sequence[ChatMessage]
    ) -> str:
        self.requests.append(LLMRequest(system_instruction, tuple(messages)))
        return self._reply

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

    async def generate(
        self, system_instruction: str, messages: Sequence[ChatMessage]
    ) -> str:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise self._error
        return await super().generate(system_instruction, messages)


class FailingLLMClient(FakeLLMClient):
    async def generate(
        self, system_instruction: str, messages: Sequence[ChatMessage]
    ) -> str:
        raise RuntimeError("the model is unavailable")


class FakeLLMClientFactory:
    def __init__(self, client: FakeLLMClient) -> None:
        self._client = client

    def create(self, _model: str) -> FakeLLMClient:
        return self._client
