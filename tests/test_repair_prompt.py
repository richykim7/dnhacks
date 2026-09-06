"""Guard repair prompt size and the scientific constraints lost by reusing extraction prompts."""
import pytest

from dnhacksbio.litmap.extract import build_repair_instructions
from dnhacksbio.litmap.vocab import (
    ASPECT_INPUTS, CATEGORIES, CLINICAL_ENDPOINTS, CONTEXT_SLOTS,
    EVIDENCE_TYPES, EXPERIMENTAL_PHENOTYPES, FUNCTIONAL_STATES, PREDICATES, STUDY_TYPES,
)


@pytest.mark.parametrize("doc_type", ["primary_research", "review"])
def test_repair_prompt_is_bounded_and_has_all_closed_values(doc_type):
    prompt = build_repair_instructions(doc_type)
    assert len(prompt) < 8000
    for menu in (ASPECT_INPUTS, CATEGORIES, CLINICAL_ENDPOINTS, EVIDENCE_TYPES,
                 EXPERIMENTAL_PHENOTYPES, FUNCTIONAL_STATES, PREDICATES, STUDY_TYPES):
        assert all(value in prompt for value in menu)
    for name, spec in CONTEXT_SLOTS.items():
        assert name in prompt
        assert all(value in prompt for value in spec.get("closed", []))
    assert "Extract every distinct scientific claim" not in prompt
    assert "Verified vocabulary supplement" not in prompt
    assert '"experiment": 0' not in prompt
    assert "Never output numeric experiment references" in prompt
    assert "singular field `experiment`, never `experiments`" in prompt


def test_repair_prompt_preserves_scope_and_does_not_inherit_review_context():
    primary = build_repair_instructions("primary_research")
    review = build_repair_instructions("review")
    assert "Context may be inherited" in primary
    assert "Review: never inherit experimental context" in review
    assert "Context may be inherited" not in review
    for prompt in (primary, review):
        assert "does not authorize guessing an ortholog" in prompt
        assert "species-specific genes still require non_human_gene" in prompt
        assert "mutations must not become a general or wild-type gene claim" in prompt
        assert "Require evidence of a measured null" in prompt
        assert "Do not strengthen the source's scientific conclusion" in prompt
        assert "never borrow a sample count from another figure panel" in prompt
