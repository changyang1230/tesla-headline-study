"""Export incidents needing human adjudication to a single JSON file for the
`tools/adjudicate.html` review UI.

The UI is read-only against the database — it never writes to `data/study.db` directly
(a browser can't). It writes decisions to a downloaded JSON file, which `apply_adjudication.py`
then applies to `incident.eligible` / `incident.index_make` / etc. That keeps human
adjudication as an explicit, auditable two-step process rather than a live DB connection
from a browser.

Usage:
    python -m src.export_adjudication --db data/study.db --out tools/adjudication_data.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3


def load_incidents(db: sqlite3.Connection, *, start: str, end: str) -> list[dict]:
    db.row_factory = sqlite3.Row
    incidents = []
    for inc in db.execute(
            "SELECT * FROM incident WHERE incident_date >= ? AND incident_date <= ? "
            "ORDER BY incident_id", (start, end)):
        inc_id = inc["incident_id"]
        coding = {r["variable"]: r["value"] for r in db.execute(
            "SELECT variable, value FROM dual_coding WHERE unit_type='incident' AND unit_id=?",
            (inc_id,))}
        coder_row = db.execute(
            "SELECT coder FROM dual_coding WHERE unit_type='incident' AND unit_id=? "
            "AND variable='index_make' LIMIT 1", (inc_id,)).fetchone()
        articles = [dict(r) for r in db.execute(
            "SELECT outlet, headline, url, headline_names_make, publish_datetime "
            "FROM article WHERE incident_id=? ORDER BY publish_datetime", (inc_id,))]
        if not articles:
            continue
        n_outlets = len({a["outlet"] for a in articles})
        incidents.append({
            "incident_id": inc_id,
            "incident_date": inc["incident_date"],
            "already_eligible": inc["eligible"],
            "already_adjudicated": inc["coded_by"] == "human_adjudication",
            "already_index_make": inc["index_make"],
            "n_outlets": n_outlets,
            "suggested_make": coding.get("index_make") or "",
            "suggested_coder": coder_row["coder"] if coder_row else None,
            "deaths": coding.get("deaths"),
            "serious_injuries": coding.get("serious_injuries"),
            "incident_type": coding.get("incident_type"),
            "second_make": coding.get("second_make"),
            "all_makes": coding.get("all_makes"),
            "make_quote": coding.get("_make_quote") or "",
            "notes": coding.get("_notes") or "",
            "review_flags": (coding.get("_review_flags") or "").split("|") if coding.get("_review_flags") else [],
            "articles": articles,
        })
    return incidents


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--out", default="tools/adjudication_data.json")
    ap.add_argument("--start", default="2025-09-01",
                    help="study window start — excludes leftover pre-pivot incidents")
    ap.add_argument("--end", default="2026-08-31", help="study window end")
    ap.add_argument("--include-decided", action="store_true",
                    help="also include incidents already adjudicated (accepted OR rejected) — "
                         "by default these are excluded so a rejected incident doesn't "
                         "silently reappear for re-review on the next export")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    incidents = load_incidents(db, start=args.start, end=args.end)
    db.close()

    if not args.include_decided:
        incidents = [i for i in incidents if not i["already_adjudicated"]]

    import pathlib
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(incidents, indent=1), encoding="utf-8")
    print(f"wrote {len(incidents)} incident(s) to {out}")


if __name__ == "__main__":
    main()
