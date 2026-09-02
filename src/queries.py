"""Frozen, brand-agnostic discovery query set (Protocol section 6.1).

THE ONE RULE: no query in this file may contain a make, model, fuel-type, or
manufacturer term. Incidents must be discoverable without the brand, or the study's
exposed and unexposed groups are ascertained by the outcome and the whole thing is
circular.

`assert_brand_agnostic()` enforces this against the lexicon and is called by the
harvester at import time and by the test suite.

FREEZE POINT: frozen at Phase 2 registration alongside the lexicon.
"""

from __future__ import annotations

import itertools
import re

from .lexicon import MAKES, normalise

# Event vocabulary. Australian headline usage: "ploughed", "smash", "come off the road".
EVENT_TERMS: tuple[str, ...] = (
    "crash",
    "crashed",
    "collision",
    "collided",
    "smash",
    "smashed",
    "head-on",
    "rollover",
    "rolled",
    "flipped",
    "overturned",
    "ploughed",
    "veered",
    "swerved",
    "hit and run",
    "car fire",
    "vehicle fire",
    "vehicle alight",
    "car alight",
    "burst into flames",
    "engulfed in flames",
    "went up in flames",
    "thermal runaway",
    "battery fire",
    "runaway car",
    "runaway vehicle",
    "struck by a car",
    "hit by a car",
    "pedestrian struck",
    "cyclist struck",
    "mowed down",
    "mows down",
    "single vehicle",
    "wrong side of the road",
    "lost control",
    "out of control",
    "off the road",
    "slammed into",
    "careered",
    "careened",
    "plunged",
    "wrapped around a pole",
    "wrapped around a tree",
    "t-boned",
    "airborne",
    "launched into",
    "car hit",
    "car hits",
    "vehicle hit",
    "vehicle hits",
    "hit by",
    "bollard",
)

#: Protocol §10.4 fallback 3 invoked 2026-08-25: 165/173 coded incidents under the
#: fatal/critical-only bar and zero were Tesla (power target was >=25) — a real
#: feasibility signal, recorded before any outcome comparison was run. Extended per the
#: fallback's own wording ("any crash with a hospitalisation or major property damage").
#: Note this only catches incidents whose HEADLINE mentions an outcome of this kind —
#: a purely novelty-framed headline ("wild crash", "chaos") with no injury/damage
#: language still won't match; that would need dropping the outcome-term requirement
#: entirely, a much larger and noisier change not implied by this fallback.
OUTCOME_TERMS: tuple[str, ...] = (
    "killed",
    "dies",
    "died",
    "dead",
    "fatal",
    "fatality",
    "critical condition",
    "serious condition",
    "life-threatening injuries",
    "trapped",
    "airlifted",
    "hospitalised",
    "hospitalized",
    "taken to hospital",
    "rushed to hospital",
    "airlifted to hospital",
    "written off",
    "extensively damaged",
    "extensive damage",
    "significant damage",
)

CONTEXT_TERMS: tuple[str, ...] = (
    "police",
    "driver",
    "road",
    "highway",
    "freeway",
    "intersection",
)

#: GDELT DOC 2.0 restricts to Australian-sourced coverage; the outlet allow-list in
#: docs/OUTLETS.md does the final filtering.
GDELT_SOURCE_FILTER = "sourcecountry:australia"


#: GDELT rejects queries over ~250 characters ("query was too short or too long"), not
#: just ones over the 250-record cap. Both event terms AND outcome terms must be chunked
#: — the full outcome OR-group alone is 171 characters, so pairing it with more than a
#: handful of event terms blows the limit. 4 event chunks x 2 outcome chunks = 8 queries
#: per window, longest observed 243 characters.
EVENT_CHUNKS = 4
OUTCOME_CHUNKS = 2


def _or_group(terms) -> str:
    return "(" + " OR ".join(f'"{t}"' for t in terms) + ")"


def _chunk(seq, n_chunks):
    size = (len(seq) + n_chunks - 1) // n_chunks
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def gdelt_queries() -> list[str]:
    """The harvest query set: OR-grouped event terms AND OR-grouped outcome terms.

    One query per (event chunk, outcome chunk) pair. Combined with daily windows in the
    harvester, this stays under GDELT's ~250-character query-length limit and its
    250-record-per-call cap, so nothing is silently truncated or rejected.
    """
    return [
        f"{_or_group(e)} {_or_group(o)} {GDELT_SOURCE_FILTER}"
        for e in _chunk(EVENT_TERMS, EVENT_CHUNKS)
        for o in _chunk(OUTCOME_TERMS, OUTCOME_CHUNKS)
    ]


#: Brands GDELT may not tag `sourcecountry:australia` because they sit on a global/foreign
#: domain. Daily Mail Australia (dailymail.com, formerly dailymail.co.uk) and bbc.com are
#: the cases that matter: both are top-10 Australian news sites by audience (Ipsos iris)
#: publishing on domains the country filter may not attribute to Australia. Dropping them
#: would bias the study toward finding nothing — they are exactly the kind of outlet most
#: inclined to put a brand in a headline.
CROSS_DOMAIN_BRANDS: tuple[str, ...] = ("dailymail.com", "theguardian.com", "bbc.com")


def gdelt_supplementary_queries() -> list[str]:
    """Domain-targeted queries for brands the country filter may miss.

    Same brand-free event vocabulary; only the source filter changes. Results still have
    to cluster onto an Australian incident to enter the study, so non-Australian coverage
    falls out at the clustering step.
    """
    return [
        f"{_or_group(e)} {_or_group(o)} domain:{brand}"
        for brand in CROSS_DOMAIN_BRANDS
        for e in _chunk(EVENT_TERMS, EVENT_CHUNKS)
        for o in _chunk(OUTCOME_TERMS, OUTCOME_CHUNKS)
    ]


def gdelt_queries_narrow() -> list[str]:
    """Cross product of event x outcome terms — the fallback if OR queries are rejected
    or if a window keeps hitting the record cap. Far slower; same coverage."""
    return [
        f'"{event}" "{outcome}" {GDELT_SOURCE_FILTER}'
        for event, outcome in itertools.product(EVENT_TERMS, OUTCOME_TERMS)
    ]


#: Deliberate decision 2026-08-25, OUTSIDE Protocol §10.4's pre-specified fallback
#: ladder (fallback 3 only widened OUTCOME_TERMS to include hospitalisation/damage
#: language — see the comment above OUTCOME_TERMS). This goes further: the outcome-term
#: co-occurrence requirement is dropped entirely, so keyword_regex() now matches on an
#: EVENT_TERMS alone. Explicitly chosen for maximum recall (catching viral/novelty
#: incidents like the DFO Homebush "runaway Tesla" story, which had a headline with no
#: injury/damage language at all) at the acknowledged cost of reintroducing the
#: circularity risk the brand-agnostic design otherwise guards against: for minor/no-
#: injury incidents, "does this get covered by media at all" becomes driven by
#: novelty rather than severity, and novelty is plausibly make-correlated (a dramatic
#: EV/autopilot incident is more newsworthy than an equivalent-severity ICE incident).
#: OUTCOME_TERMS is kept, unused by this function, for any future severity tagging.
REQUIRE_OUTCOME_TERM = False


def keyword_regex() -> re.Pattern[str]:
    """Local re-filter for harvests that arrive without server-side query support."""
    ev = "|".join(re.escape(t) for t in EVENT_TERMS)
    if not REQUIRE_OUTCOME_TERM:
        return re.compile(rf"(?:{ev})", re.IGNORECASE | re.DOTALL)
    oc = "|".join(re.escape(t) for t in OUTCOME_TERMS)
    return re.compile(rf"(?=.*(?:{ev}))(?=.*(?:{oc}))", re.IGNORECASE | re.DOTALL)


def assert_brand_agnostic() -> None:
    """Fail loudly if any brand term has leaked into the query set.

    This is the guard on the study's central validity threat, so it raises rather than
    warns, and it runs on import of the harvester.
    """
    brand_tokens = set()
    for m in MAKES:
        brand_tokens.update(normalise(a) for a in m.aliases)
        brand_tokens.update(normalise(x) for x in m.models)
    brand_tokens.update({"electric", "ev", "hybrid", "petrol", "diesel", "luxury", "suv brand"})

    for term in EVENT_TERMS + OUTCOME_TERMS + CONTEXT_TERMS + CROSS_DOMAIN_BRANDS:
        t = normalise(term)
        for b in brand_tokens:
            if b and re.search(rf"(?<![\w]){re.escape(b)}(?![\w])", t):
                raise AssertionError(
                    f"Brand term {b!r} leaked into discovery query {term!r}. "
                    "This would make incident discovery depend on the outcome "
                    "(Protocol section 6.1)."
                )


assert_brand_agnostic()
