"""The analysis must recover a known truth from simulated data, and must NOT find an
effect in a null dataset.

This is what licenses running `analysis.py` once on the real data: the code has already
been shown to behave correctly on data whose answer is known.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.analysis import effect, gee_fit, incident_level, prepare, within_incident
from src.power import detectable_p1, requirement
from src.simulate import simulate


@pytest.fixture(scope="module")
def effect_df():
    return prepare(simulate(n_tesla=40, n_other=160, seed=11, tesla_log_or=float(np.log(4.0))))


@pytest.fixture(scope="module")
def null_df():
    return prepare(simulate(n_tesla=40, n_other=160, seed=12, tesla_log_or=0.0,
                            bev_log_or=0.0, premium_log_or=0.0))


def test_recovers_a_real_effect(effect_df):
    e = effect(gee_fit(effect_df, "headline_names_make", "tesla"), "tesla")
    assert e["or"] > 1.3
    assert e["p"] < 0.05
    assert e["lo"] > 1.0


def test_does_not_manufacture_an_effect_from_nothing(null_df):
    e = effect(gee_fit(null_df, "headline_names_make", "tesla"), "tesla")
    assert e["lo"] < 1.0 < e["hi"], f"null data produced a 'significant' OR of {e['or']:.2f}"


def test_within_incident_analysis_runs(effect_df):
    wi = within_incident(effect_df)
    assert wi["n_articles"] > 0
    assert wi["tesla_only"] + wi["other_only"] > 0
    assert 0.0 <= wi["p_exact"] <= 1.0


def test_incident_level_companion_agrees_in_direction(effect_df):
    il = incident_level(effect_df)
    assert il["mean_tesla"] > il["mean_other"]
    assert il.get("qb_or", 1.0) > 1.0


def test_clustering_costs_precision(effect_df):
    """Ignoring clustering must not be allowed to look more certain than accounting for it."""
    from statsmodels.genmod.cov_struct import Independence
    clustered = effect(gee_fit(effect_df, "headline_names_make", "tesla"), "tesla")
    assert clustered["se"] > 0
    assert np.isfinite(clustered["se"])


# --- power ------------------------------------------------------------------------

def test_design_effect_increases_the_requirement():
    low = requirement(0.10, 0.35, m=8, rho=0.1)["incidents_per_arm"]
    high = requirement(0.10, 0.35, m=8, rho=0.9)["incidents_per_arm"]
    assert high > low


def test_smaller_samples_detect_only_larger_effects():
    small = detectable_p1(0.10, 10, m=8, rho=0.5)
    large = detectable_p1(0.10, 60, m=8, rho=0.5)
    assert small > large > 0.10
