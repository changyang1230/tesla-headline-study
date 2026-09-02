"""Merge incidents that clustering split into multiple `incident` rows despite being the
same real-world crash — usually because coverage spread across several days (a crash
report, then a bail hearing, then a court update) fell outside `cluster_incidents.py`'s
similarity window, or because articles used different enough phrasing to not cluster.

This is a distinct failure mode from `apply_cluster_review.py`'s "article doesn't belong
to this incident" flag: here, every article DOES belong together, they're just split
across the wrong number of incident rows instead of one.

All of the merged-away incidents' articles are re-pointed onto the canonical incident;
the merged-away incident rows are kept (not deleted) with `eligible=0` and an
`exclusion_reason` noting the merge, so the audit trail survives. `incident_date` is left
as whatever the canonical incident already has — pick the earliest-dated one as canonical
so the date reflects the actual crash, not a later follow-up story.

Usage:
    python -m src.merge_incidents --db data/study.db --into 20251114-NSW-01 \
        --merge 20251115-01 20251121-01 [--second-make Kia]
"""

from __future__ import annotations

import argparse
import sqlite3


def merge_incidents(db: sqlite3.Connection, canonical: str, merge_ids: list[str],
                     *, second_make: str | None = None) -> dict:
    stats = {"articles_relinked": 0, "incidents_merged": 0}
    row = db.execute("SELECT incident_id FROM incident WHERE incident_id=?", (canonical,)).fetchone()
    if not row:
        raise SystemExit(f"canonical incident {canonical!r} not found")

    for mid in merge_ids:
        if mid == canonical:
            continue
        row = db.execute("SELECT incident_id FROM incident WHERE incident_id=?", (mid,)).fetchone()
        if not row:
            continue
        n = db.execute(
            "UPDATE article SET incident_id=? WHERE incident_id=?", (canonical, mid)
        ).rowcount
        stats["articles_relinked"] += n
        db.execute(
            "UPDATE incident SET eligible=0, "
            "exclusion_reason=?, coded_by='human_adjudication', coded_at=datetime('now') "
            "WHERE incident_id=?",
            (f"merged into {canonical}: same real-world crash, split by clustering error", mid))
        stats["incidents_merged"] += 1

    if second_make:
        db.execute("UPDATE incident SET second_make=? WHERE incident_id=?", (second_make, canonical))

    db.commit()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--into", required=True, help="canonical incident_id to keep")
    ap.add_argument("--merge", required=True, nargs="+", help="incident_id(s) to merge into --into")
    ap.add_argument("--second-make", default=None,
                     help="optionally set the canonical incident's second_make")
    args = ap.parse_args()

    db = sqlite3.connect(args.db, timeout=60.0)
    db.execute("PRAGMA busy_timeout = 60000")
    stats = merge_incidents(db, args.into, args.merge, second_make=args.second_make)
    db.close()
    print(stats)


if __name__ == "__main__":
    main()
