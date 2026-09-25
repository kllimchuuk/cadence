import uuid

from orchestration.prompts import build_persona_system_prompt
from persona.models import PersonaMemory
from scenarios.config import get_scenario


def _persona_memory(facts: list[str]) -> PersonaMemory:
    return PersonaMemory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        scenario_id="job_interview",
        facts=facts,
    )


def test_the_prompt_names_the_scenarios_role_and_persona_and_goals() -> None:
    scenario = get_scenario("job_interview")

    prompt = build_persona_system_prompt(scenario, persona_memory=None)

    assert scenario.persona in prompt
    assert scenario.role in prompt
    for goal in scenario.goal_checklist:
        assert goal in prompt


def test_the_prompt_includes_remembered_facts_when_present() -> None:
    scenario = get_scenario("job_interview")
    memory = _persona_memory(["User is preparing for a backend interview."])

    prompt = build_persona_system_prompt(scenario, memory)

    assert "User is preparing for a backend interview." in prompt


def test_the_prompt_omits_the_memory_section_when_there_is_none() -> None:
    scenario = get_scenario("job_interview")

    prompt = build_persona_system_prompt(scenario, persona_memory=None)

    assert "remember" not in prompt.lower()


def test_the_prompt_omits_the_memory_section_when_facts_are_empty() -> None:
    scenario = get_scenario("job_interview")
    memory = _persona_memory([])

    prompt = build_persona_system_prompt(scenario, memory)

    assert "remember" not in prompt.lower()
