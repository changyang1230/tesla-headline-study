"""Assertions for the primary analysis — the two conditional probabilities.

This is the study, so these are the tests that matter most. In particular they pin down
the clustering claim: the permutation test must be materially more conservative than
Fisher on the same data, because that difference is the whole reason the permutation
p is the one reported.
"""

from __future__ import annotations

import random

import pytest

from src.primary import (build_report, fisher_exact, newcombe_diff, permutation_p,
                         to_incidents, wilson)


# --- interval estimation ---------------------------------------------------------

def test_wilson_brackets_the_point_estimate():
    lo, hi = wilson(45, 100)
    assert lo < 0.45 < hi


def test_wilson_handles_zero_and_one_without_collapsing():
    """Wald gives a zero-width interval at k=0; Wilson must not."""
    lo, hi = wilson(0, 30)
    assert lo == 0.0 and hi > 0.0
    lo, hi = wilson(30, 30)
    assert hi == 1.0 and lo < 1.0


def test_wilson_narrows_with_n():
    small = wilson(5, 10)
    large = wilson(500, 1000)
    assert (large[1] - large[0]) < (small[1] - small[0])


def test_newcombe_difference_brackets_the_observed_difference():
    lo, hi = newcombe_diff(45, 100, 25, 100)
    assert lo < 0.20 < hi


def test_newcombe_excludes_zero_for_a_clear_difference():
    lo, hi = newcombe_diff(90, 100, 10, 100)
    assert lo > 0


# --- Fisher exact (stdlib implementation) ----------------------------------------

def test_fisher_matches_scipy():
    scipy_stats = pytest.importorskip("scipy.stats")
    for table in [(10, 90, 5, 95), (45, 55, 25, 75), (3, 7, 8, 2), (1, 9, 9, 1)]:
        mine = fisher_exact(*table)
        theirs = scipy_stats.fisher_exact([[table[0], table[1]], [table[2], table[3]]])[1]
        assert mine == pytest.approx(theirs, rel=1e-9), table


def test_fisher_is_one_for_identical_proportions():
    assert fisher_exact(10, 10, 10, 10) == pytest.approx(1.0)


# --- the clustering claim --------------------------------------------------------

def _incidents(n_tesla, n_other, k_per_tesla, k_per_other, n_articles=8):
    """Fixed counts per incident — for testing direction, not p-value calibration."""
    out = []
    for i in range(n_tesla):
        out.append({"incident_id": f"T{i}", "k": k_per_tesla, "n": n_articles,
                    "tesla": 1, "make": "Tesla", "prop": k_per_tesla / n_articles})
    for i in range(n_other):
        out.append({"incident_id": f"O{i}", "k": k_per_other, "n": n_articles,
                    "tesla": 0, "make": "Toyota", "prop": k_per_other / n_articles})
    return out


def _independent(n_tesla, n_other, p_tesla, p_other, seed, n_articles=8):
    """Each article decided independently — NO clustering. Fisher is correct here."""
    r = random.Random(seed)
    out = []
    for label, count, prob in ((1, n_tesla, p_tesla), (0, n_other, p_other)):
        for i in range(count):
            k = sum(1 for _ in range(n_articles) if r.random() < prob)
            out.append({"incident_id": f"{'T' if label else 'O'}{i}", "k": k,
                        "n": n_articles, "tesla": label,
                        "make": "Tesla" if label else "Toyota", "prop": k / n_articles})
    return out


def _clustered(n_tesla, n_other, p_tesla, p_other, seed, n_articles=8):
    """The incident decides and every outlet follows — maximal clustering.

    This is the realistic shape: whether the make is "the story" is settled once, at the
    incident level, and the other outlets copy it.
    """
    r = random.Random(seed)
    out = []
    for label, count, prob in ((1, n_tesla, p_tesla), (0, n_other, p_other)):
        for i in range(count):
            k = n_articles if r.random() < prob else 0
            out.append({"incident_id": f"{'T' if label else 'O'}{i}", "k": k,
                        "n": n_articles, "tesla": label,
                        "make": "Tesla" if label else "Toyota", "prop": k / n_articles})
    return out


def _both_p(incidents, n_perm=3000):
    _, perm = permutation_p(incidents, n_perm=n_perm, seed=1)
    k1 = sum(i["k"] for i in incidents if i["tesla"])
    n1 = sum(i["n"] for i in incidents if i["tesla"])
    k0 = sum(i["k"] for i in incidents if not i["tesla"])
    n0 = sum(i["n"] for i in incidents if not i["tesla"])
    return perm, fisher_exact(k1, n1 - k1, k0, n0 - k0)


def test_permutation_agrees_with_fisher_when_there_is_no_clustering():
    """The permutation test must not be conservative for its own sake.

    With every article decided independently, Fisher's independence assumption holds and
    the two p-values should land in the same place.
    """
    perm, fisher = _both_p(_independent(15, 45, 0.32, 0.25, seed=11))
    assert 0.4 < perm / fisher < 3.0, f"perm {perm:.4g} vs fisher {fisher:.4g}"


def test_permutation_is_vastly_more_conservative_when_clustering_is_real():
    """The reason the permutation p is the one reported."""
    perm, fisher = _both_p(_clustered(25, 75, 0.60, 0.20, seed=0))
    assert perm > fisher * 1000, f"perm {perm:.4g} vs fisher {fisher:.4g}"


def test_fisher_can_declare_significance_where_the_honest_test_does_not():
    """The failure mode this guards against, on one concrete dataset.

    Fisher sees p < 1e-6 and calls it decisive. Accounting for the fact that the 800
    articles describe only 100 incidents, the difference is not significant at all.
    """
    perm, fisher = _both_p(_clustered(25, 75, 0.60, 0.20, seed=5))
    assert fisher < 1e-5
    assert perm > 0.05


def test_permutation_finds_a_real_difference():
    incs = _incidents(n_tesla=20, n_other=60, k_per_tesla=7, k_per_other=1)
    observed, p = permutation_p(incs, n_perm=3000, seed=2)
    assert observed > 0
    assert p < 0.01


def test_permutation_stays_null_when_arms_are_identical():
    incs = _incidents(n_tesla=20, n_other=60, k_per_tesla=3, k_per_other=3)
    observed, p = permutation_p(incs, n_perm=2000, seed=3)
    assert observed == pytest.approx(0.0)
    assert p > 0.5


def test_permutation_p_is_never_zero():
    """Add-one correction — a permutation p of exactly 0 would be a lie."""
    incs = _incidents(n_tesla=25, n_other=75, k_per_tesla=8, k_per_other=0)
    _, p = permutation_p(incs, n_perm=500, seed=4)
    assert p > 0


def test_permutation_is_deterministic_for_a_fixed_seed():
    incs = _incidents(10, 30, 5, 2)
    assert permutation_p(incs, n_perm=800, seed=7) == permutation_p(incs, n_perm=800, seed=7)


# --- eligibility threshold -------------------------------------------------------

def _articles(inc, outlets, named):
    return [{"incident_id": inc, "outlet": o, "headline_names_make": int(i < named),
             "tesla": 1, "index_make": "Tesla", "make_tier": "1"}
            for i, o in enumerate(outlets)]


def test_incidents_below_the_coverage_threshold_are_dropped():
    rows = _articles("A", ["news.com.au", "ABC News", "9News", "7NEWS", "The Age"], 3)
    rows += _articles("B", ["news.com.au", "ABC News"], 1)
    kept, dropped = to_incidents(rows, min_outlets=5)
    assert [i["incident_id"] for i in kept] == ["A"]
    assert sum(dropped.values()) == 1


def test_threshold_is_on_distinct_brands_not_article_count():
    """Five articles from two brands is two brands, not five."""
    rows = _articles("A", ["news.com.au"] * 3 + ["ABC News"] * 2, 5)
    kept, _ = to_incidents(rows, min_outlets=5)
    assert kept == []


def test_tier1_filter_drops_media_dependent_makes():
    rows = _articles("A", ["news.com.au", "ABC News", "9News", "7NEWS", "The Age"], 3)
    for r in rows:
        r["make_tier"] = "2"
    kept, dropped = to_incidents(rows, min_outlets=5, tier1_only=True)
    assert kept == []
    assert any("tier 2" in k for k in dropped)


# --- report ----------------------------------------------------------------------

def test_report_states_both_probabilities_and_the_permutation_p():
    incs = _incidents(n_tesla=15, n_other=45, k_per_tesla=5, k_per_other=1)
    text = build_report(incs, {}, {}, "test", min_outlets=5, n_perm=500)
    assert "p(make in title" not in text  # the report shows numbers, not notation
    assert "**Tesla**" in text and "**Not Tesla**" in text
    assert "permutation test" in text
    assert "By make" in text


def test_report_survives_an_empty_arm_without_crashing():
    incs = _incidents(n_tesla=0, n_other=10, k_per_tesla=0, k_per_other=2)
    text = build_report(incs, {}, {}, "test", min_outlets=5, n_perm=100)
    assert "one of the two arms is empty" in text
