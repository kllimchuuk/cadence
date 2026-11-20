import uuid

from progress.models import SessionProgress
from progress.report import Direction, build_report


def _progress(
    grammar_issues: int = 0, goals_achieved: int = 0, learner_words: int = 100
) -> SessionProgress:
    return SessionProgress(
        session_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        grammar_issue_count=grammar_issues,
        vocabulary_issue_count=0,
        goals_achieved=goals_achieved,
        goals_total=4,
        learner_word_count=learner_words,
        total_word_count=200,
    )


def test_rates_are_derived_from_the_stored_counts() -> None:
    progress = _progress(grammar_issues=3, goals_achieved=2, learner_words=150)

    assert progress.grammar_issue_rate == 2.0
    assert progress.goal_completion_rate == 0.5
    assert progress.learner_word_share == 0.75


def test_rates_of_an_empty_session_are_zero() -> None:
    progress = SessionProgress(
        grammar_issue_count=4,
        vocabulary_issue_count=4,
        goals_achieved=0,
        goals_total=0,
        learner_word_count=0,
        total_word_count=0,
    )

    assert progress.grammar_issue_rate == 0.0
    assert progress.vocabulary_issue_rate == 0.0
    assert progress.goal_completion_rate == 0.0
    assert progress.learner_word_share == 0.0


def test_there_is_no_trend_before_a_second_session() -> None:
    report = build_report([_progress()])

    assert report.trend.grammar_issue_rate is None
    assert report.trend.goal_completion_rate is None


def test_the_report_has_no_trend_for_a_learner_without_sessions() -> None:
    report = build_report([])

    assert report.sessions == []
    assert report.trend.learner_word_share is None


def test_fewer_grammar_issues_than_the_baseline_is_an_improvement() -> None:
    report = build_report([_progress(grammar_issues=8), _progress(grammar_issues=2)])

    trend = report.trend.grammar_issue_rate
    assert trend is not None
    assert (trend.baseline, trend.latest) == (8.0, 2.0)
    assert trend.direction == Direction.IMPROVING


def test_more_grammar_issues_than_the_baseline_is_a_decline() -> None:
    report = build_report([_progress(grammar_issues=2), _progress(grammar_issues=8)])

    trend = report.trend.grammar_issue_rate
    assert trend is not None
    assert trend.direction == Direction.DECLINING


def test_a_higher_goal_completion_is_an_improvement() -> None:
    report = build_report([_progress(goals_achieved=1), _progress(goals_achieved=4)])

    trend = report.trend.goal_completion_rate
    assert trend is not None
    assert trend.direction == Direction.IMPROVING


def test_a_small_change_is_steady() -> None:
    report = build_report([_progress(grammar_issues=20), _progress(grammar_issues=21)])

    trend = report.trend.grammar_issue_rate
    assert trend is not None
    assert trend.direction == Direction.STEADY


def test_two_clean_sessions_in_a_row_are_steady() -> None:
    report = build_report([_progress(grammar_issues=0), _progress(grammar_issues=0)])

    trend = report.trend.grammar_issue_rate
    assert trend is not None
    assert trend.direction == Direction.STEADY


def test_the_baseline_only_looks_at_the_three_sessions_before_the_latest() -> None:
    sessions = [
        _progress(grammar_issues=50),
        _progress(grammar_issues=10),
        _progress(grammar_issues=10),
        _progress(grammar_issues=10),
        _progress(grammar_issues=10),
    ]

    trend = build_report(sessions).trend.grammar_issue_rate

    assert trend is not None
    assert trend.baseline == 10.0
    assert trend.direction == Direction.STEADY
