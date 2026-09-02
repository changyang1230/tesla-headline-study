"""Split an `incident` row that clustering wrongly merged from two or more distinct
real-world crashes — the opposite failure mode from `merge_incidents.py`. Usually caused
by generic phrasing overlap (e.g. two unrelated crashes both mentioning "Hume Highway")
that the cosine-similarity clustering treats as the same event.

Moves the given articles off the original incident onto a brand-new incident row (created
here), and resets the original incident's `index_make`/`second_make`/`eligible` so it gets
recoded and re-adjudicated against only the articles that actually remain — a make
determined from mixed, contaminated body text cannot be trusted even if it happens to
still be correct.

Usage:
    python -m src.split_incident --db data/study.db --from 20260213-NSW-01 \
        --new-id 20260214-NSW-01 --new-date 2026-02-14 \
        --move-articles <article_id> [<article_id> ...] \
        [--new-index-make Toyota --new-second-make "Alfa Romeo" --new-eligible]
"""

from __future__ import annotations

import argparse
import sqlite3


def split_incident(db: sqlite3.Connection, *, from_id: str, new_id: str, new_date: str,
                    move_article_ids: list[str], new_index_make: str | None = None,
                    new_second_make: str | None = None, new_eligible: bool = False) -> dict:
    row = db.execute("SELECT incident_id FROM incident WHERE incident_id=?", (from_id,)).fetchone()
    if not row:
        raise SystemExit(f"source incident {from_id!r} not found")
    existing = db.execute("SELECT incident_id FROM incident WHERE incident_id=?", (new_id,)).fetchone()
    if existing:
        raise SystemExit(f"target incident_id {new_id!r} already exists")

    db.execute(
        "INSERT INTO incident (incident_id, incident_date, eligible, index_make, second_make, "
        "multi_vehicle, coded_by, coded_at, notes) VALUES (?,?,?,?,?,?,?,datetime('now'),?)",
        (new_id, new_date, int(new_eligible), new_index_make, new_second_make,
         int(bool(new_second_make)), "human_adjudication" if new_eligible else "claude_suggested_pending_confirmation",
         f"Split from {from_id}: clustering had merged a distinct real-world crash into "
         f"that incident's article set."))

    placeholders = ",".join("?" * len(move_article_ids))
    n_moved = db.execute(
        f"UPDATE article SET incident_id=? WHERE article_id IN ({placeholders})",
        (new_id, *move_article_ids)).rowcount

    db.execute(
        "UPDATE incident SET index_make=NULL, second_make=NULL, multi_vehicle=0, eligible=0, "
        "coded_by='needs_recoding', coded_at=datetime('now'), "
        "notes=? WHERE incident_id=?",
        (f"Split {new_id} off this incident (clustering contamination); remaining "
         f"articles need fresh make coding/adjudication, previous index_make was "
         f"determined from mixed, contaminated body text.", from_id))

    db.commit()
    return {"new_incident": new_id, "articles_moved": n_moved, "source_reset": from_id}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--from", dest="from_id", required=True)
    ap.add_argument("--new-id", required=True)
    ap.add_argument("--new-date", required=True)
    ap.add_argument("--move-articles", nargs="+", required=True)
    ap.add_argument("--new-index-make", default=None)
    ap.add_argument("--new-second-make", default=None)
    ap.add_argument("--new-eligible", action="store_true",
                     help="mark the new incident eligible=1 immediately (only if the make "
                          "determination is already confirmed, e.g. via an explicit Codebook rule)")
    args = ap.parse_args()

    db = sqlite3.connect(args.db, timeout=60.0)
    db.execute("PRAGMA busy_timeout = 60000")
    stats = split_incident(
        db, from_id=args.from_id, new_id=args.new_id, new_date=args.new_date,
        move_article_ids=args.move_articles, new_index_make=args.new_index_make,
        new_second_make=args.new_second_make, new_eligible=args.new_eligible)
    db.close()
    print(stats)


if __name__ == "__main__":
    main()
