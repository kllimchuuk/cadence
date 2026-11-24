from collections.abc import Iterable
from dataclasses import dataclass

from analysis.models import SessionAnalysis
from llm.client import MessageRole
from practice.models import LearningSession
from scenarios.config import get_scenario


@dataclass(frozen=True)
class SessionMetrics:
    grammar_issue_count: int
    vocabulary_issue_count: int
    goals_achieved: int
    goals_total: int
    learner_word_count: int
    total_word_count: int


def _word_count(turns: Iterable[dict[str, str]]) -> int:
    return sum(len(turn["content"].split()) for turn in turns)


def measure_session(
    learning_session: LearningSession, analysis: SessionAnalysis
) -> SessionMetrics:
    transcript = learning_session.transcript or []
    goals_total = len(get_scenario(learning_session.scenario_id).goal_checklist)
    goals_achieved = sum(goal["achieved"] for goal in analysis.task_completion["goals"])
    return SessionMetrics(
        grammar_issue_count=len(analysis.grammar_findings),
        vocabulary_issue_count=len(analysis.vocabulary_findings),
        goals_achieved=min(goals_achieved, goals_total),
        goals_total=goals_total,
        learner_word_count=_word_count(
            turn for turn in transcript if turn["role"] == MessageRole.USER
        ),
        total_word_count=_word_count(transcript),
    )
