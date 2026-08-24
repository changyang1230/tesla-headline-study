"""Assertions for the LLM-assisted coding safeguards (Protocol section 8.2).

These test the safeguards, not the model. The model's accuracy is measured by
`validate_coding.py` against a hand-coded gold standard; what is testable here is that
the machinery around it cannot leak the headline or touch the outcome.
"""

from __future__ import annotations

import pytest

from src.llm_coding import (CONFIDENCE_FLOOR, FORBIDDEN_FIELDS, SCHEMA, build_prompt,
                            needs_review, strip_headlines)
from src.validate_coding import MAX_ASCERTAINMENT_DIFFERENTIAL, cohens_kappa, report


# --- safeguard 1: headline blinding ------------------------------------------------

def test_headline_is_stripped_from_body():
    body = "Tesla driver killed in Monash crash\nA man has died after his car left the road."
    out = strip_headlines(body, "Tesla driver killed in Monash crash")
    assert "killed in Monash crash" not in out
    assert "A man has died" in out


def test_headline_stripped_despite_punctuation_drift():
    """Scraped pages routinely repeat the headline with different punctuation."""
    body = "Tesla  driver   killed, in Monash crash\nPolice attended the scene."
    out = strip_headlines(body, "Tesla driver killed in Monash crash")
    assert "Police attended" in out
    assert "Monash crash" not in out.split("\n")[0]


def test_standfirst_is_also_stripped():
    out = strip_headlines("HL\nSF\nBody text here.", "HL", "SF")
    assert "Body text here." in out
    assert out.strip().startswith("Body")


def test_all_caps_lead_line_is_dropped():
    out = strip_headlines("TESLA DRIVER KILLED IN CRASH\nA man has died.")
    assert "TESLA DRIVER KILLED" not in out


def test_prompt_never_contains_the_headline():
    articles = [{"outlet": "ABC News", "headline": "Tesla driver killed in Monash crash",
                 "standfirst": "", "body": "Tesla driver killed in Monash crash\n"
                                           "A man has died on the freeway."}]
    prompt = build_prompt("I1", articles)
    assert "killed in Monash crash" not in prompt
    assert "A man has died" in prompt
    assert "Headlines have been removed" in prompt


# --- safeguard 2: the model never codes the outcome --------------------------------

def test_outcome_fields_are_absent_from_the_extraction_schema():
    assert not (FORBIDDEN_FIELDS & set(SCHEMA["properties"]))


def test_schema_forbids_extra_properties():
    """additionalProperties: false is what makes the forbidden-field guarantee hold."""
    assert SCHEMA["additionalProperties"] is False


def test_eligibility_is_not_a_model_decision():
    assert "eligible" in FORBIDDEN_FIELDS
    assert "eligible" not in SCHEMA["properties"]


# --- safeguard 3: low confidence and missing evidence get flagged ------------------

def test_low_confidence_is_flagged():
    flags = needs_review({"deaths": 2, "confidence": {"deaths": CONFIDENCE_FLOOR - 0.1},
                          "evidence": {"deaths": "two people died"}})
    assert any("deaths" in f and "low_confidence" in f for f in flags)


def test_missing_evidence_is_flagged():
    flags = needs_review({"deaths": 2, "confidence": {"deaths": 0.99}, "evidence": {}})
    assert any("deaths" in f and "no_evidence" in f for f in flags)


def test_ambiguous_index_vehicle_is_flagged():
    assert "index_vehicle_ambiguous" in needs_review(
        {"index_vehicle_ambiguous": True, "confidence": {}, "evidence": {}})


def test_confident_well_evidenced_coding_passes_clean():
    assert needs_review({"deaths": 2, "index_make": "Tesla", "make_source_quote": "the Tesla",
                         "confidence": {"deaths": 0.95, "index_make": 0.98},
                         "evidence": {"deaths": "two died", "index_make": "the Tesla"}}) == []


# --- validation: the differential check --------------------------------------------

def _gold_and_machine(tesla_recall: float, other_recall: float, n: int = 20):
    gold, machine = {}, {}
    common = {"state": "VIC", "deaths": "1", "incident_type": "occupant_fatal_collision"}
    for i in range(n):
        hit = i < round(tesla_recall * n)
        gold[f"T{i}"] = {"index_make": "Tesla", **common}
        machine[f"T{i}"] = {"index_make": "Tesla" if hit else "", **common}
    for i in range(n):
        hit = i < round(other_recall * n)
        gold[f"O{i}"] = {"index_make": "Toyota", **common}
        machine[f"O{i}"] = {"index_make": "Toyota" if hit else "", **common}
    return gold, machine


def test_lopsided_make_recovery_fails_validation():
    """The failure mode that would manufacture the entire effect."""
    _, passed = report(*_gold_and_machine(tesla_recall=1.0, other_recall=0.5))
    assert not passed


def test_even_make_recovery_passes_the_differential():
    text, _ = report(*_gold_and_machine(tesla_recall=0.95, other_recall=0.95))
    assert "EXCEEDS" not in text
    assert "within" in text


def test_differential_limit_is_tight():
    assert MAX_ASCERTAINMENT_DIFFERENTIAL <= 0.10


def test_missing_tesla_gold_standard_fails_rather_than_passing_silently():
    gold = {"O1": {"index_make": "Toyota", "state": "VIC"}}
    machine = {"O1": {"index_make": "Toyota", "state": "VIC"}}
    text, passed = report(gold, machine)
    assert not passed
    assert "Not enough Tesla incidents" in text


# --- kappa ---------------------------------------------------------------------

def test_kappa_perfect_and_chance():
    assert cohens_kappa([("a", "a"), ("b", "b"), ("a", "a"), ("b", "b")]) == pytest.approx(1.0)
    assert cohens_kappa([("a", "a")] * 4) is None       # single label: undefined
    mixed = cohens_kappa([("a", "b"), ("b", "a"), ("a", "b"), ("b", "a")])
    assert mixed is not None and mixed < 0
