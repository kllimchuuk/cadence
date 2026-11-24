from dataclasses import dataclass

from scenarios.exceptions import UnknownScenarioError


@dataclass(frozen=True)
class Scenario:
    id: str
    role: str
    persona: str
    goal_checklist: tuple[str, ...]
    difficulty: str
    trains_skills: tuple[str, ...]


_EVERY_CONVERSATION: tuple[str, ...] = (
    "articles",
    "subject_verb_agreement",
    "negation_and_auxiliaries",
)

_SCENARIOS: dict[str, Scenario] = {
    scenario.id: scenario
    for scenario in (
        Scenario(
            id="job_interview",
            role="a hiring manager running a technical job interview",
            persona=(
                "Priya, a backend engineering manager who interviews candidates "
                "for a mid-level role. Professional but warm, and asks follow-up "
                "questions instead of accepting vague answers."
            ),
            goal_checklist=(
                "greet the candidate and set expectations for the interview",
                "ask about the candidate's relevant experience",
                "probe at least one technical claim with a follow-up question",
                "give the candidate a chance to ask questions",
            ),
            difficulty="intermediate",
            trains_skills=(
                "present_perfect_vs_past_simple",
                "irregular_past_forms",
                "tense_consistency",
                "question_word_order",
                *_EVERY_CONVERSATION,
            ),
        ),
        Scenario(
            id="daily_standup",
            role="a teammate running a daily stand-up meeting",
            persona=(
                "Sam, a friendly team lead who keeps stand-ups short and "
                "expects yesterday/today/blockers, not a status essay."
            ),
            goal_checklist=(
                "report what was done yesterday",
                "report what is planned for today",
                "mention any blockers, or state there are none",
            ),
            difficulty="beginner",
            trains_skills=(
                "irregular_past_forms",
                "present_simple_vs_continuous",
                "future_forms",
                "tense_consistency",
                *_EVERY_CONVERSATION,
            ),
        ),
        Scenario(
            id="client_call",
            role="a client on a project status update call",
            persona=(
                "Alex, a non-technical client who wants a clear progress "
                "update and gets anxious about vague timelines."
            ),
            goal_checklist=(
                "summarise current progress in plain, non-technical language",
                "address at least one risk or delay honestly",
                "confirm the next milestone and rough timeline",
            ),
            difficulty="intermediate",
            trains_skills=(
                "present_perfect_vs_past_simple",
                "future_forms",
                "conditionals",
                "modal_verbs",
                "countable_uncountable_nouns",
                "reported_speech",
                *_EVERY_CONVERSATION,
            ),
        ),
        Scenario(
            id="small_talk_networking",
            role="a stranger at a networking event",
            persona=(
                "Jordan, an outgoing attendee at a tech meetup who enjoys "
                "casual conversation and asks open follow-up questions."
            ),
            goal_checklist=(
                "introduce yourself and what you do",
                "ask the other person something about themselves",
                "find and continue at least one shared topic",
            ),
            difficulty="beginner",
            trains_skills=(
                "present_simple_vs_continuous",
                "question_word_order",
                "gerund_vs_infinitive",
                "prepositions_of_place",
                *_EVERY_CONVERSATION,
            ),
        ),
        Scenario(
            id="presentation_qa",
            role="an audience member during a presentation Q&A",
            persona=(
                "Morgan, an engaged audience member who asks pointed but fair "
                "questions after a talk."
            ),
            goal_checklist=(
                "answer the question directly before elaborating",
                "handle at least one follow-up or clarifying question",
                "stay composed when challenged on a point",
            ),
            difficulty="advanced",
            trains_skills=(
                "comparatives_superlatives",
                "conditionals",
                "relative_clauses",
                "reported_speech",
                "modal_verbs",
                *_EVERY_CONVERSATION,
            ),
        ),
        Scenario(
            id="phone_booking",
            role="a receptionist taking a phone booking",
            persona=(
                "Taylor, a polite receptionist booking an appointment over the "
                "phone, who confirms details back before finishing the call."
            ),
            goal_checklist=(
                "state the purpose of the call",
                "agree on a specific date and time",
                "confirm contact details for the booking",
            ),
            difficulty="beginner",
            trains_skills=(
                "prepositions_of_time",
                "modal_verbs",
                "question_word_order",
                "future_forms",
                *_EVERY_CONVERSATION,
            ),
        ),
    )
}


def list_scenarios() -> tuple[Scenario, ...]:
    return tuple(_SCENARIOS.values())


def get_scenario(scenario_id: str) -> Scenario:
    try:
        return _SCENARIOS[scenario_id]
    except KeyError:
        raise UnknownScenarioError(scenario_id) from None
