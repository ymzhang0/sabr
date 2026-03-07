from src.sab_engines.aiida.agent.prompts import (
    SUBMISSION_DRAFT_REQUIRED_RULE,
    build_system_prompt,
)


def test_build_system_prompt_includes_submission_draft_required_rule() -> None:
    prompt = build_system_prompt()
    assert SUBMISSION_DRAFT_REQUIRED_RULE in prompt
    assert "PROFILE DISCIPLINE" in prompt
    assert "At most one automatic profile switch is allowed in a turn" in prompt


def test_build_system_prompt_injects_skill_overlays_and_htp_constraints() -> None:
    prompt = build_system_prompt(
        skill_overlays=["Use cautious retries", "Prioritize reproducibility"],
        htp_constraints=["Bundle all selected structures into one draft payload"],
        extra_instructions=["Never skip validation"],
    )
    assert "### SKILL OVERLAYS" in prompt
    assert "- Use cautious retries" in prompt
    assert "- Prioritize reproducibility" in prompt
    assert "### HTP CONSTRAINTS" in prompt
    assert "- Bundle all selected structures into one draft payload" in prompt
    assert "### ADDITIONAL INSTRUCTIONS" in prompt
    assert "- Never skip validation" in prompt
