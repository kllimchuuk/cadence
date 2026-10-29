import re
from collections.abc import Sequence

from analysis.schemas import SessionAnalysisResult

_NON_WORD = re.compile(r"[\W_]+")


def _normalize(text: str) -> str:
    return _NON_WORD.sub(" ", text.casefold()).strip()


def learner_turns(transcript: Sequence[dict[str, str]]) -> list[str]:
    return [
        f" {_normalize(turn['content'])} "
        for turn in transcript
        if turn["role"] == "user"
    ]


def _is_quoted(evidence: str, turns: Sequence[str]) -> bool:
    quote = _normalize(evidence)
    return bool(quote) and any(f" {quote} " in turn for turn in turns)


def find_unquoted_evidence(
    result: SessionAnalysisResult, turns: Sequence[str]
) -> list[str]:
    evidence = [
        *(observation.evidence for observation in result.skill_observations),
        *(fact.evidence for fact in result.new_facts),
    ]
    return [quote for quote in evidence if not _is_quoted(quote, turns)]


def keep_quoted(
    result: SessionAnalysisResult, turns: Sequence[str]
) -> SessionAnalysisResult:
    return result.model_copy(
        update={
            "skill_observations": [
                observation
                for observation in result.skill_observations
                if _is_quoted(observation.evidence, turns)
            ],
            "new_facts": [
                fact for fact in result.new_facts if _is_quoted(fact.evidence, turns)
            ],
        }
    )
