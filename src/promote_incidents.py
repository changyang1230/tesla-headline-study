"""Promote eligible candidate clusters (output/candidate_incidents.csv) into real
`incident` + `article` rows, fetching real body text along the way.

This is a DRAFT promotion, not the protocol's Step 4/5 manual verification — every
incident it creates is inserted with `eligible=0` and `notes` flagging it as
auto-promoted. It exists so real article text is on disk and make-identification can
start (Codebook 8.2's LLM-assisted coding, headline-blinded, written to `dual_coding`
only — never to `incident.index_make` directly) without waiting on the full manual
clustering calibration this project's protocol otherwise requires before trusting a
cluster as "one real incident."

Usage:
    python -m src.promote_incidents --db data/study.db --csv output/candidate_incidents.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sqlite3

from .fetch_bodies import article_id, fetch_one

LOG = logging.getLogger("promote_incidents")

#: Very rough locality -> state hints. State is no longer required to promote an
#: incident (dropped 2026-08-25 — not used by the primary analysis, only ever an
#: appendix covariate, and requiring it silently blocked real incidents whose headline
#: never named a state — e.g. the Ed Husic Tesla crash, whose headlines just said
#: "serious car crash"). Kept as a best-effort optional fill for anyone who wants it.
STATE_HINTS = {
    "nsw": "NSW", "sydney": "NSW", "hunter valley": "NSW", "greta": "NSW",
    "ashcroft": "NSW", "monterey": "NSW", "newcastle": "NSW", "wollongong": "NSW",
    "vic": "VIC", "victoria": "VIC", "melbourne": "VIC", "geelong": "VIC",
    "qld": "QLD", "queensland": "QLD", "brisbane": "QLD", "gold coast": "QLD",
    "wa": "WA", "perth": "WA",
    "sa": "SA", "adelaide": "SA",
    "tas": "TAS", "hobart": "TAS",
    "nt": "NT", "darwin": "NT", "northern territory": "NT",
    "act": "ACT", "canberra": "ACT",
}


def guess_state(text: str) -> str | None:
    t = text.lower()
    for hint, state in STATE_HINTS.items():
        if hint in t:
            return state
    return None


def next_seq(db: sqlite3.Connection, date_str: str) -> int:
    prefix = f"{date_str.replace('-', '')}-"
    existing = [r[0] for r in db.execute(
        "SELECT incident_id FROM incident WHERE incident_id LIKE ?", (prefix + "%",))]
    nums = []
    for e in existing:
        tail = e.rsplit("-", 1)[1]
        if tail.isdigit():
            nums.append(int(tail))
    return (max(nums) + 1) if nums else 1


def promote_cluster(db: sqlite3.Connection, cluster_id: str, urls: list[str],
                     example_headlines: str, first_seen: str) -> str | None:
    state = guess_state(example_headlines) or guess_state(urls[0])  # best-effort, optional

    seq = next_seq(db, first_seen)
    incident_id = f"{first_seen.replace('-', '')}-{seq:02d}"

    db.execute(
        "INSERT INTO incident (incident_id, incident_date, state, eligible, coded_by, notes) "
        "VALUES (?,?,?,0,?,?)",
        (incident_id, first_seen, state, "auto_promote",
         f"Draft promotion from cluster {cluster_id}; state guessed from headline text; "
         "NOT protocol Step 4/5 verified; needs human review before eligible=1."))

    linked = 0
    for url in urls:
        row = db.execute(
            "SELECT url_hash, canonical_url, domain, seendate FROM harvest WHERE canonical_url=?",
            (url,)).fetchone()
        if not row:
            continue
        aid = fetch_one(db, row["url_hash"], row["canonical_url"], row["domain"],
                         row["domain"], row["seendate"])
        if aid:
            db.execute("UPDATE article SET incident_id=? WHERE article_id=?", (incident_id, aid))
            linked += 1
    db.commit()
    LOG.info("%s: promoted %d/%d articles fetched and linked", incident_id, linked, len(urls))
    return incident_id


def augment_incident(db: sqlite3.Connection, incident_id: str, urls: list[str]) -> int:
    """Link any of `urls` not yet linked to ANY incident onto this existing one.

    Re-clustering after new harvest data lands can grow a cluster that already has a
    promoted incident — e.g. two news.com.au articles about the same crash arriving via a
    later manual sitemap import. Without this, those URLs are silently never linked
    anywhere: the old dedup-by-URL check in `main()` sees the cluster overlaps an
    existing incident and skips the whole cluster, including the genuinely new URLs.
    Found 2026-08-25 via the Ed Husic Tesla incident (20260806-NSW-01): it sat at 2-outlet
    coverage, just under the eligibility bar, while a re-cluster showed a 4th article
    (a 3rd outlet) that had never been linked despite being in `harvest` and correctly
    classified as a vehicle crash.
    """
    linked = 0
    for url in urls:
        row = db.execute(
            "SELECT url_hash, canonical_url, domain, seendate FROM harvest WHERE canonical_url=?",
            (url,)).fetchone()
        if not row:
            continue
        existing_article = db.execute(
            "SELECT article_id, incident_id FROM article WHERE article_id=?",
            (article_id(url),)).fetchone()
        if existing_article and existing_article["incident_id"]:
            continue  # already linked (possibly to this same incident) — nothing to do
        aid = fetch_one(db, row["url_hash"], row["canonical_url"], row["domain"],
                         row["domain"], row["seendate"])
        if aid:
            db.execute("UPDATE article SET incident_id=? WHERE article_id=?", (incident_id, aid))
            linked += 1
    if linked:
        db.commit()
    return linked


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--csv", default="output/candidate_incidents.csv")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    db = sqlite3.connect(args.db, timeout=60.0)
    db.execute("PRAGMA busy_timeout = 60000")
    db.row_factory = sqlite3.Row

    with open(args.csv) as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[:args.limit]

    promoted = []
    for row in rows:
        urls = row["urls"].split()
        if not urls:
            continue
        # Dedup on the cluster's actual URLs, not the cluster_id label — cluster IDs
        # (C0001, C0002...) are NOT stable across re-clustering runs (new harvest data
        # reshuffles ordering), so label-based dedup silently re-promotes the same real
        # incident under a new ID every time this is re-run against fresh data. That bug
        # ran undetected through the night: the same Wardell NSW crash was promoted 5
        # times as 5 different incident_ids, each re-promotion stealing its articles'
        # incident_id link from the previous one via the UPDATE below, leaving 4 orphaned
        # empty incident rows. Checking article-level state directly is robust to label
        # churn because it's keyed on the URL itself, not on which run discovered it.
        aids = [article_id(u) for u in urls]
        placeholders = ",".join("?" * len(aids))
        existing = db.execute(
            f"SELECT DISTINCT incident_id FROM article "
            f"WHERE article_id IN ({placeholders}) AND incident_id IS NOT NULL", aids).fetchall()
        if existing:
            distinct_ids = {r["incident_id"] for r in existing}
            if len(distinct_ids) == 1:
                inc_id = next(iter(distinct_ids))
                n = augment_incident(db, inc_id, urls)
                if n:
                    LOG.info("%s: %d new article(s) linked onto existing %s",
                             row["cluster_id"], n, inc_id)
                else:
                    LOG.info("%s: already fully linked to %s, skipping",
                             row["cluster_id"], inc_id)
            else:
                LOG.warning("%s: URLs span multiple existing incidents %s — ambiguous "
                            "merge, needs human review, skipping",
                            row["cluster_id"], distinct_ids)
            continue
        inc = promote_cluster(db, row["cluster_id"], urls, row["example_headlines"], row["first_seen"])
        if inc:
            promoted.append(inc)

    LOG.info("done: promoted %d incidents: %s", len(promoted), promoted)


if __name__ == "__main__":
    main()
