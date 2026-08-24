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
    "head-on",
    "rollover",
    "rolled",
    "ploughed",
    "veered",
    "hit and run",
    "car fire",
    "vehicle fire",
    "vehicle alight",
    "car alight",
    "struck by a car",
    "hit by a car",
    "pedestrian struck",
    "cyclist struck",
    "single vehicle",
    "wrong side of the road",
)

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


#: GDELT rejects very long/complex queries, so event terms are OR-ed in chunks rather
#: than as one enormous disjunction. Four chunks x daily windows keeps every call under
#: the 250-record cap while finishing a five-year harvest in a few hours.
EVENT_CHUNKS = 4


def _or_group(terms) -> str:
    return "(" + " OR ".join(f'"{t}"' for t in terms) + ")"


def gdelt_queries() -> list[str]:
    """The harvest query set: OR-grouped event terms AND OR-grouped outcome terms.

    One query per event chunk. Combined with daily windows in the harvester, this stays
    well under GDELT's 250-record-per-call cap, so nothing is silently truncated, while
    keeping the call count to a few thousand rather than sixty thousand.
    """
    outcome = _or_group(OUTCOME_TERMS)
    chunk = (len(EVENT_TERMS) + EVENT_CHUNKS - 1) // EVENT_CHUNKS
    return [
        f"{_or_group(EVENT_TERMS[i:i + chunk])} {outcome} {GDELT_SOURCE_FILTER}"
        for i in range(0, len(EVENT_TERMS), chunk)
    ]


def gdelt_queries_narrow() -> list[str]:
    """Cross product of event x outcome terms — the fallback if OR queries are rejected
    or if a window keeps hitting the record cap. Far slower; same coverage."""
    return [
        f'"{event}" "{outcome}" {GDELT_SOURCE_FILTER}'
        for event, outcome in itertools.product(EVENT_TERMS, OUTCOME_TERMS)
    ]


def keyword_regex() -> re.Pattern[str]:
    """Local re-filter for harvests that arrive without server-side query support."""
    ev = "|".join(re.escape(t) for t in EVENT_TERMS)
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

    for term in EVENT_TERMS + OUTCOME_TERMS + CONTEXT_TERMS:
        t = normalise(term)
        for b in brand_tokens:
            if b and re.search(rf"(?<![\w]){re.escape(b)}(?![\w])", t):
                raise AssertionError(
                    f"Brand term {b!r} leaked into discovery query {term!r}. "
                    "This would make incident discovery depend on the outcome "
                    "(Protocol section 6.1)."
                )


assert_brand_agnostic()
