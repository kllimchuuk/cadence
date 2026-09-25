from dataclasses import dataclass

from scenarios.exceptions import UnknownScenarioError


@dataclass(frozen=True)
class Scenario:
    id: str
    role: str
    persona: str
    goal_checklist: tuple[str, ...]
    difficulty: str


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
        ),
    )
}


def get_scenario(scenario_id: str) -> Scenario:
    try:
        return _SCENARIOS[scenario_id]
    except KeyError:
        raise UnknownScenarioError(scenario_id) from None
