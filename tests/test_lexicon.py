"""Assertions for the frozen lexicon and query set.

The primary outcome is produced mechanically by `lexicon.py`, so these tests ARE the
outcome definition. Every Codebook section 3 rule appears here as an executable assertion,
and every false positive found in Phase 0 must be added as a case before the lexicon is
changed.

Run:  python -m pytest research/tesla-headline-salience/tests -q
"""

from __future__ import annotations

import pytest

from src.lexicon import (AMBIGUOUS_MODEL_TOKENS, MAKES, canonical_make, identified_makes,
                         names_make, normalise)
from src.queries import EVENT_TERMS, OUTCOME_TERMS, assert_brand_agnostic, gdelt_queries


# --- Codebook 3.1: matching -------------------------------------------------------

@pytest.mark.parametrize("headline,make", [
    ("Tesla crashes into shopfront killing two", "Tesla"),
    ("Teslas recalled after Sydney crash", "Tesla"),
    ("Tesla's driver charged over fatal collision", "Tesla"),
    ("TESLA DRIVER DIES IN HUME HIGHWAY SMASH", "Tesla"),
    ("Mercedes-Benz driver killed at intersection", "Mercedes-Benz"),
    ("Merc driver charged after Perth crash", "Mercedes-Benz"),
    ("Range Rover ploughs into cafe", "Land Rover"),
])
def test_make_token_matches(headline, make):
    assert names_make(headline, make)


def test_word_boundaries_are_respected():
    assert not names_make("Teslarati reviews the new sedan", "Tesla")
    assert not names_make("Fordham speaks on radio", "Ford")


def test_unicode_and_punctuation_are_normalised():
    assert names_make("Tesla’s driver dies", "Tesla")
    assert normalise("Head–on  crash") == "head-on crash"


# --- Codebook 3.2: model tokens count as make identification ----------------------

@pytest.mark.parametrize("headline,make", [
    ("Model 3 driver dies on Hume Highway", "Tesla"),
    ("Model-Y bursts into flames in Chatswood carpark", "Tesla"),
    ("Cybertruck involved in Melbourne collision", "Tesla"),
    ("HiLux ploughs into shopfront", "Toyota"),
    ("Ford Ranger rolls on Bruce Highway", "Ford"),
    ("LandCruiser rollover kills two", "Toyota"),
])
def test_model_tokens_identify_the_make(headline, make):
    assert names_make(headline, make)


def test_strict_mode_excludes_model_tokens():
    """The pre-specified sensitivity definition (Protocol 7.3)."""
    assert names_make("Model 3 driver dies", "Tesla")
    assert not names_make("Model 3 driver dies", "Tesla", strict=True)
    assert names_make("Tesla Model 3 driver dies", "Tesla", strict=True)


def test_ambiguous_tokens_are_not_in_the_lexicon():
    """Counting 'Focus' or 'Escape' as a Ford would bias toward the hypothesis."""
    used = {m for mk in MAKES for m in mk.models}
    assert not (used & AMBIGUOUS_MODEL_TOKENS)
    assert not names_make("Police focus on driver after fatal crash", "Ford")
    assert not names_make("Narrow escape as car hits pole", "Ford")


# --- Codebook 3.3: disambiguation -------------------------------------------------

@pytest.mark.parametrize("headline,make", [
    ("Nikola Tesla museum plans unveiled", "Tesla"),
    ("Patient dies during 3 tesla MRI scan", "Tesla"),
    ("Tesla coil display draws crowds", "Tesla"),
    ("Tesla shares tumble after recall", "Tesla"),
    ("Park ranger finds crashed vehicle in bushland", "Ford"),
    ("Kia Ora festival draws thousands", "Kia"),
    ("Man given 500 mg of morphine dies in custody", "MG"),
    ("Ram raid on jewellery store", "RAM"),
    ("Taylor Swift concert traffic chaos", "Suzuki"),
    ("Shark attack closes beach", "BYD"),
])
def test_rejection_contexts(headline, make):
    assert not names_make(headline, make)


# --- multi-make headlines (the within-incident matched analysis) ------------------

def test_multiple_makes_in_one_headline():
    got = identified_makes("Tesla and Toyota HiLux collide on Monash Freeway")
    assert got == {"Tesla", "Toyota"}


def test_model_only_headline_identifies_both_makes():
    assert identified_makes("Model 3 and HiLux collide") == {"Tesla", "Toyota"}
    assert identified_makes("Model 3 and HiLux collide", strict=True) == set()


# --- Codebook 1.4: make normalisation ---------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Mercedes", "Mercedes-Benz"), ("merc", "Mercedes-Benz"),
    ("VW", "Volkswagen"), ("Volkswagon", "Volkswagen"),
    ("Range Rover", "Land Rover"), ("TESLA", "Tesla"),
])
def test_canonical_make(raw, expected):
    assert canonical_make(raw) == expected


def test_unknown_make_returns_none():
    assert canonical_make("Delorean") is None


# --- Protocol 6.1: the central validity guard -------------------------------------

def test_query_set_contains_no_brand_terms():
    """If this ever fails, incident discovery depends on the outcome and the study is
    circular. It is the single most important assertion in the suite."""
    assert_brand_agnostic()


def test_no_brand_string_appears_anywhere_in_the_query_set():
    blob = " ".join(gdelt_queries()).lower()
    for mk in MAKES:
        for alias in mk.aliases:
            assert alias.lower() not in blob, f"{alias} leaked into the query set"


def test_query_terms_are_event_vocabulary_only():
    assert all(EVENT_TERMS) and all(OUTCOME_TERMS)
    assert "electric" not in " ".join(EVENT_TERMS + OUTCOME_TERMS).lower()
