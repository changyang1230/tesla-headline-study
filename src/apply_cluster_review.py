"""Apply cluster-review flags (from `tools/review_clusters.html`'s downloaded JSON) by
marking the flagged articles `excluded=1` — they stop counting toward incident outlet
coverage and toward `headline_names_make` aggregation (`v_analysis` filters on
`a.excluded = 0`), without deleting anything or touching `incident.eligible`.

This does NOT re-cluster or re-promote. If a flagged article was the thing making an
incident meet the ≥2-outlet threshold, that incident will now silently drop below
threshold at analysis time (via `primary.py`'s own outlet count) — it does not need to be
re-adjudicated as ineligible; the mechanism already handles it.

Usage:
    python -m src.apply_cluster_review --db data/study.db --flags ~/Downloads/cluster_review_flags.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3


def apply_flags(db: sqlite3.Connection, flags: list[dict]) -> dict:
    stats = {"excluded": 0, "skipped_unknown_article": 0}
    for f in flags:
        aid = f["article_id"]
        row = db.execute("SELECT article_id FROM article WHERE article_id=?", (aid,)).fetchone()
        if not row:
            stats["skipped_unknown_article"] += 1
            continue
        db.execute(
            "UPDATE article SET excluded=1, "
            "exclusion_reason='human-flagged: does not belong to this incident (cluster review)' "
            "WHERE article_id=?", (aid,))
        stats["excluded"] += 1
    db.commit()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--flags", required=True)
    args = ap.parse_args()

    flags = json.loads(open(args.flags, encoding="utf-8").read())
    db = sqlite3.connect(args.db, timeout=60.0)
    db.execute("PRAGMA busy_timeout = 60000")
    stats = apply_flags(db, flags)
    db.close()
    print(stats)


if __name__ == "__main__":
    main()
