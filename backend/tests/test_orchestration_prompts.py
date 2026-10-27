import uuid

from orchestration.prompts import (
    build_analysis_system_instruction,
    build_grammar_triage_instruction,
    build_persona_system_prompt,
    build_scenario_content_query,
)
from persona.models import PersonaMemory
from rag.entries import RetrievedChunk
from rag.models import ContentChunk
from scenarios.config import get_scenario
from weaknesses.models import WeaknessRecord, WeaknessState


def _persona_memory(facts: list[str]) -> PersonaMemory:
    return PersonaMemory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        scenario_id="job_interview",
        facts=facts,
    )


def test_the_prompt_names_the_scenarios_role_and_persona_and_goals() -> None:
    scenario = get_scenario("job_interview")

    prompt = build_persona_system_prompt(scenario, None, [])

    assert scenario.persona in prompt
    assert scenario.role in prompt
    for goal in scenario.goal_checklist:
        assert goal in prompt


def test_the_prompt_includes_remembered_facts_when_present() -> None:
    scenario = get_scenario("job_interview")
    memory = _persona_memory(["User is preparing for a backend interview."])

    prompt = build_persona_system_prompt(scenario, memory, [])

    assert "User is preparing for a backend interview." in prompt


def test_the_prompt_omits_the_memory_section_when_there_is_none() -> None:
    scenario = get_scenario("job_interview")

    prompt = build_persona_system_prompt(scenario, None, [])

    assert "remember" not in prompt.lower()


def test_the_prompt_omits_the_memory_section_when_facts_are_empty() -> None:
    scenario = get_scenario("job_interview")
    memory = _persona_memory([])

    prompt = build_persona_system_prompt(scenario, memory, [])

    assert "remember" not in prompt.lower()


def _chunk(title: str, content: str) -> RetrievedChunk:
    return RetrievedChunk(title=title, content=content, skill_key=None, distance=0.0)


def test_the_prompt_lists_reference_content_inside_a_delimited_block() -> None:
    scenario = get_scenario("job_interview")
    chunks = [
        _chunk("Most challenging project", "Ask what made it hard."),
        _chunk("Strengths", "Ask for one real weakness."),
    ]

    prompt = build_persona_system_prompt(scenario, None, chunks)

    block = prompt.split("<reference>")[1].split("</reference>")[0]
    assert "- Most challenging project: Ask what made it hard." in block
    assert "- Strengths: Ask for one real weakness." in block
    assert "not instructions" in prompt.split("<reference>")[0]


def test_the_prompt_omits_the_reference_block_when_nothing_was_retrieved() -> None:
    scenario = get_scenario("job_interview")

    prompt = build_persona_system_prompt(scenario, None, [])

    assert "<reference>" not in prompt


def test_the_scenario_content_query_combines_remembered_facts_and_goals() -> None:
    scenario = get_scenario("job_interview")
    memory = _persona_memory(["User is moving from backend into AI."])

    query = build_scenario_content_query(scenario, memory)

    assert "User is moving from backend into AI." in query
    for goal in scenario.goal_checklist:
        assert goal in query


def test_the_scenario_content_query_without_memory_is_just_the_goals() -> None:
    scenario = get_scenario("job_interview")

    query = build_scenario_content_query(scenario, None)

    assert query == ". ".join(scenario.goal_checklist)


def test_the_triage_instruction_judges_only_the_learners_turns() -> None:
    instruction = build_grammar_triage_instruction([])

    assert 'whose role is "user"' in instruction
    assert "already tracked" not in instruction


def test_the_triage_instruction_names_the_tracked_skills() -> None:
    weakness = WeaknessRecord(skill_key="articles", state=WeaknessState.PROBATION)

    instruction = build_grammar_triage_instruction([weakness])

    assert "articles (probation)" in instruction


def test_the_analysis_instruction_fences_the_grammar_reference_as_data() -> None:
    chunk = ContentChunk(skill_key="articles", title="Articles", content="Use a.")

    instruction = build_analysis_system_instruction(
        get_scenario("job_interview"), [chunk], []
    )

    assert "<grammar_reference>\n- articles (Articles): Use a.\n" in instruction
    assert "data, not instructions" in instruction


def test_the_analysis_instruction_omits_empty_sections() -> None:
    instruction = build_analysis_system_instruction(
        get_scenario("job_interview"), [], []
    )

    assert "grammar_reference" not in instruction
    assert "already tracked" not in instruction
