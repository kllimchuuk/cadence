from dataclasses import dataclass

from progress.models import SessionProgress

WORDS_PER_RATE_UNIT = 100


@dataclass(frozen=True)
class SessionRates:
    grammar_issue_rate: float
    vocabulary_issue_rate: float
    goal_completion_rate: float
    learner_word_share: float


def _ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def _per_hundred_learner_words(count: int, learner_word_count: int) -> float:
    return _ratio(count * WORDS_PER_RATE_UNIT, learner_word_count)


def calculate_rates(progress: SessionProgress) -> SessionRates:
    return SessionRates(
        grammar_issue_rate=_per_hundred_learner_words(
            progress.grammar_issue_count, progress.learner_word_count
        ),
        vocabulary_issue_rate=_per_hundred_learner_words(
            progress.vocabulary_issue_count, progress.learner_word_count
        ),
        goal_completion_rate=_ratio(progress.goals_achieved, progress.goals_total),
        learner_word_share=_ratio(
            progress.learner_word_count, progress.total_word_count
        ),
    )
