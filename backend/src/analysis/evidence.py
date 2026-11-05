import re
from collections.abc import Sequence
from typing import Protocol, TypeVar

from analysis.schemas import SessionAnalysisResult, TaskCompletion
from llm.client import MessageRole

MIN_QUOTE_WORDS = 2

_NON_WORD = re.compile(r"[\W_]+")


class _Quoted(Protocol):
    evidence: str


_QuotedT = TypeVar("_QuotedT", bound=_Quoted)


def _normalize(text: str) -> str:
    return _NON_WORD.sub(" ", text.casefold()).strip()


def learner_turns(transcript: Sequence[dict[str, str]]) -> list[str]:
    return [
        f" {_normalize(turn['content'])} "
        for turn in transcript
        if turn["role"] == MessageRole.USER
    ]


def _is_quoted(evidence: str, turns: Sequence[str]) -> bool:
    quote = _normalize(evidence)
    if len(quote.split()) < MIN_QUOTE_WORDS:
        return False
    return any(f" {quote} " in turn for turn in turns)


def find_unquoted_evidence(
    result: SessionAnalysisResult, turns: Sequence[str]
) -> list[str]:
    quotes = [
        *(observation.evidence for observation in result.skill_observations),
        *(fact.evidence for fact in result.new_facts),
        *(finding.evidence for finding in result.grammar_findings),
        *(finding.evidence for finding in result.vocabulary_findings),
        *(goal.evidence for goal in result.task_completion.goals if goal.achieved),
        *(point.evidence for point in result.focus_points),
    ]
    return [quote for quote in quotes if not _is_quoted(quote, turns)]


def _quoted(items: Sequence[_QuotedT], turns: Sequence[str]) -> list[_QuotedT]:
    return [item for item in items if _is_quoted(item.evidence, turns)]


def keep_quoted(
    result: SessionAnalysisResult, turns: Sequence[str]
) -> SessionAnalysisResult:
    goals = [
        goal
        for goal in result.task_completion.goals
        if not goal.achieved or _is_quoted(goal.evidence, turns)
    ]
    return result.model_copy(
        update={
            "skill_observations": _quoted(result.skill_observations, turns),
            "new_facts": _quoted(result.new_facts, turns),
            "grammar_findings": _quoted(result.grammar_findings, turns),
            "vocabulary_findings": _quoted(result.vocabulary_findings, turns),
            "task_completion": TaskCompletion(goals=goals),
            "focus_points": _quoted(result.focus_points, turns),
        }
    )
