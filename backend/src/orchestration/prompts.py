from persona.models import PersonaMemory
from scenarios.config import Scenario


def build_persona_system_prompt(
    scenario: Scenario, persona_memory: PersonaMemory | None
) -> str:
    lines = [
        f"You are role-playing as {scenario.persona}",
        f"This is a {scenario.role} practice scenario for an English learner.",
        "Guide the conversation toward these goals: "
        + "; ".join(scenario.goal_checklist)
        + ".",
    ]
    if persona_memory is not None and persona_memory.facts:
        lines.append(
            "What you remember about this person from earlier sessions: "
            + "; ".join(persona_memory.facts)
        )
    return "\n".join(lines)
