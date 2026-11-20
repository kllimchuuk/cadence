from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

from progress.models import SessionProgress

BASELINE_SESSIONS = 3
STEADY_TOLERANCE = 0.1


class Direction(StrEnum):
    IMPROVING = "improving"
    STEADY = "steady"
    DECLINING = "declining"


@dataclass(frozen=True)
class MetricTrend:
    baseline: float
    latest: float
    direction: Direction


@dataclass(frozen=True)
class ProgressTrend:
    grammar_issue_rate: MetricTrend | None
    vocabulary_issue_rate: MetricTrend | None
    goal_completion_rate: MetricTrend | None
    learner_word_share: MetricTrend | None


@dataclass(frozen=True)
class ProgressReport:
    sessions: list[SessionProgress]
    trend: ProgressTrend


def _direction(baseline: float, latest: float, higher_is_better: bool) -> Direction:
    change = latest - baseline
    if abs(change) <= STEADY_TOLERANCE * abs(baseline):
        return Direction.STEADY
    if (change > 0) == higher_is_better:
        return Direction.IMPROVING
    return Direction.DECLINING


def _metric_trend(
    sessions: Sequence[SessionProgress],
    metric: Callable[[SessionProgress], float],
    higher_is_better: bool,
) -> MetricTrend | None:
    if len(sessions) < 2:
        return None
    values = [metric(session) for session in sessions]
    baseline = fmean(values[-1 - BASELINE_SESSIONS : -1])
    latest = values[-1]
    return MetricTrend(baseline, latest, _direction(baseline, latest, higher_is_better))


def build_report(sessions: list[SessionProgress]) -> ProgressReport:
    return ProgressReport(
        sessions=sessions,
        trend=ProgressTrend(
            grammar_issue_rate=_metric_trend(
                sessions, lambda s: s.grammar_issue_rate, higher_is_better=False
            ),
            vocabulary_issue_rate=_metric_trend(
                sessions, lambda s: s.vocabulary_issue_rate, higher_is_better=False
            ),
            goal_completion_rate=_metric_trend(
                sessions, lambda s: s.goal_completion_rate, higher_is_better=True
            ),
            learner_word_share=_metric_trend(
                sessions, lambda s: s.learner_word_share, higher_is_better=True
            ),
        ),
    )
