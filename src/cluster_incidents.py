"""Cluster harvested articles into candidate incidents (Protocol section 6.3).

Output is a *candidate* list for manual verification, never a final incident register.
Clustering headlines is approximate; a five-fatality crash and a separate fatal crash in
the same suburb on the same day look similar to a cosine, and only a human can tell them
apart. `--out` writes a review CSV; the verified rows are what get loaded into
`incident`.

Clustering may use brand tokens to *merge* articles. It must never use them to *include*
an article — inclusion is decided by the frozen brand-agnostic query set at harvest time.

Usage:
    python -m src.cluster_incidents --db data/study.db --out output/candidate_incidents.csv
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import logging
import math
import pathlib
import re
import sqlite3

from .gdelt_harvest import NON_COUNTING_GROUPS, OUTLET_DOMAINS
from .queries import EVENT_TERMS, OUTCOME_TERMS

LOG = logging.getLogger("cluster")

DATE_WINDOW_DAYS = 3
COSINE_THRESHOLD = 0.35
#: Two articles also link if they share this many corpus-rare tokens. Locality names
#: ("daylesford", "wangaratta") are the strongest incident signal in a headline, and this
#: rule catches pairs whose cosine is diluted by differing event vocabulary.
RARE_SHARED_TOKENS = 2
RARE_DF_FRACTION = 0.002     # a token is "rare" if it appears in <0.2% of harvested headlines
MIN_OUTLET_GROUPS = 3        # Protocol section 6.4 eligibility

#: Both thresholds are provisional. Phase 0 calibrates them against a hand-labelled
#: sample of ~200 articles and records the chosen values in output/phase0_feasibility.md
#: before the frame is built. Calibrating on clustering quality alone is safe: the
#: clusterer never sees the outcome.

#: Words carrying no discriminating information here. The event vocabulary is in every
#: harvested headline by construction, so leaving it in would make everything look alike.
_STOP = set("""
a an the and or of in on at to for with from by as is are was were be been being this that
after before over under into out up down off near amid says said say new man woman boy girl
people person police year old years two three four five one his her their its it he she they
australia australian australias
""".split())
_STOP |= {w for t in EVENT_TERMS + OUTCOME_TERMS for w in re.findall(r"[a-z]+", t.lower())}

_WORD = re.compile(r"[a-z][a-z'\-]+|\d+")


def tokenise(title: str) -> list[str]:
    return [w for w in _WORD.findall((title or "").lower()) if w not in _STOP and len(w) > 2]


def _tfidf(docs: list[list[str]]) -> tuple[list[dict[str, float]], collections.Counter[str], int]:
    df: collections.Counter[str] = collections.Counter()
    for d in docs:
        df.update(set(d))
    n = max(len(docs), 1)
    vecs = []
    for d in docs:
        tf = collections.Counter(d)
        v = {w: (c / len(d)) * math.log((n + 1) / (df[w] + 1)) for w, c in tf.items()} if d else {}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({w: x / norm for w, x in v.items()})
    return vecs, df, n


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0.0) for w, x in a.items())


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))

    def find(self, i: int) -> int:
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.p[rj] = ri


def _parse_seendate(s: str | None) -> dt.date | None:
    if not s:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def cluster(rows: list[sqlite3.Row], *, threshold: float = COSINE_THRESHOLD) -> list[list[int]]:
    """Union-find over articles within the date window that are similar enough.

    Two linkage criteria, either sufficient: headline cosine at or above `threshold`, or
    at least RARE_SHARED_TOKENS shared corpus-rare tokens (typically a locality name).
    """
    docs = [tokenise(r["title_at_crawl"]) for r in rows]
    vecs, df, n = _tfidf(docs)
    rare_cut = max(2, int(n * RARE_DF_FRACTION))
    rare_sets = [{w for w in set(d) if df[w] <= rare_cut} for d in docs]
    dates = [_parse_seendate(r["seendate"]) for r in rows]

    # Bucket by date so the comparison stays near-linear instead of O(n^2) over the
    # whole study period.
    buckets: dict[dt.date, list[int]] = collections.defaultdict(list)
    for i, d in enumerate(dates):
        if d:
            buckets[d].append(i)

    uf = _UnionFind(len(rows))
    for d, idxs in buckets.items():
        neighbours = [j for k in range(-DATE_WINDOW_DAYS, DATE_WINDOW_DAYS + 1)
                      for j in buckets.get(d + dt.timedelta(days=k), [])]
        for i in idxs:
            for j in neighbours:
                if j <= i:
                    continue
                if (cosine(vecs[i], vecs[j]) >= threshold
                        or len(rare_sets[i] & rare_sets[j]) >= RARE_SHARED_TOKENS):
                    uf.union(i, j)

    groups: dict[int, list[int]] = collections.defaultdict(list)
    for i in range(len(rows)):
        groups[uf.find(i)].append(i)
    return sorted(groups.values(), key=len, reverse=True)


def counting_groups(rows: list[sqlite3.Row], idxs: list[int]) -> set[str]:
    out = set()
    for i in idxs:
        meta = OUTLET_DOMAINS.get(rows[i]["domain"])
        if meta and meta[1] not in NON_COUNTING_GROUPS:
            out.add(meta[1])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--out", default="output/candidate_incidents.csv")
    ap.add_argument("--min-groups", type=int, default=MIN_OUTLET_GROUPS)
    ap.add_argument("--threshold", type=float, default=COSINE_THRESHOLD,
                    help="cosine linkage threshold; calibrate in Phase 0")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    rows = list(db.execute(
        "SELECT url_hash, canonical_url, domain, title_at_crawl, seendate FROM harvest"))
    LOG.info("clustering %d harvested articles", len(rows))

    clusters = cluster(rows, threshold=args.threshold)
    kept = [c for c in clusters if len(counting_groups(rows, c)) >= args.min_groups]
    LOG.info("%d clusters, %d meeting the >=%d outlet-group threshold",
             len(clusters), len(kept), args.min_groups)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cluster_id", "n_articles", "n_outlet_groups", "first_seen",
                    "example_headlines", "urls",
                    # blank columns for the human reviewer (Codebook section 1)
                    "VERIFIED_single_incident", "incident_date", "state", "locality",
                    "deaths", "index_make", "make_tier", "make_source", "eligible",
                    "exclusion_reason", "reviewer", "notes"])
        for cid, idxs in enumerate(kept, start=1):
            dates = sorted(d for d in (_parse_seendate(rows[i]["seendate"]) for i in idxs) if d)
            w.writerow([
                f"C{cid:04d}", len(idxs), len(counting_groups(rows, idxs)),
                dates[0].isoformat() if dates else "",
                " || ".join((rows[i]["title_at_crawl"] or "")[:120] for i in idxs[:5]),
                " ".join(rows[i]["canonical_url"] for i in idxs),
                "", "", "", "", "", "", "", "", "", "", "", "",
            ])
    LOG.info("wrote %s — every row needs manual verification before it becomes an incident", out)


if __name__ == "__main__":
    main()
