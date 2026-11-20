from analysis.models import SessionAnalysis
from practice.models import LearningSession
from progress.metrics import SessionMetrics, measure_session

TRANSCRIPT = [
    {"role": "assistant", "content": "Good morning, what did you do yesterday?"},
    {"role": "user", "content": "Yesterday I go to the office."},
    {"role": "assistant", "content": "And today?"},
    {"role": "user", "content": "Today I fix a bug."},
]


def _learning_session(transcript: list | None) -> LearningSession:
    return LearningSession(scenario_id="daily_standup", transcript=transcript)


def _analysis(
    grammar_findings: int = 0, vocabulary_findings: int = 0, goals: list | None = None
) -> SessionAnalysis:
    return SessionAnalysis(
        grammar_findings=[{}] * grammar_findings,
        vocabulary_findings=[{}] * vocabulary_findings,
        task_completion={"goals": goals or []},
    )


def test_a_session_is_measured_from_its_transcript_and_analysis() -> None:
    goals = [{"achieved": True}, {"achieved": False}, {"achieved": True}]

    metrics = measure_session(
        _learning_session(TRANSCRIPT),
        _analysis(grammar_findings=2, vocabulary_findings=1, goals=goals),
    )

    assert metrics == SessionMetrics(
        grammar_issue_count=2,
        vocabulary_issue_count=1,
        goals_achieved=2,
        goals_total=3,
        learner_word_count=11,
        total_word_count=20,
    )


def test_achieved_goals_never_exceed_the_scenarios_checklist() -> None:
    goals = [{"achieved": True}] * 5

    metrics = measure_session(_learning_session(TRANSCRIPT), _analysis(goals=goals))

    assert metrics.goals_achieved == metrics.goals_total == 3


def test_a_session_without_a_transcript_has_no_words() -> None:
    metrics = measure_session(_learning_session(None), _analysis())

    assert metrics.learner_word_count == 0
    assert metrics.total_word_count == 0
