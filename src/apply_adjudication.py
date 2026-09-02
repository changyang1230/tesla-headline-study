"""Apply human adjudication decisions (from `tools/adjudicate.html`'s downloaded JSON)
into `incident.eligible` / `incident.index_make` / `incident.exclusion_reason`.

This is the only place anything writes to `incident.eligible` or `incident.index_make` for
real (non-simulated) data — everything upstream of this deliberately stops at `dual_coding`.
`coded_by`/`coded_at` are set so it's visible in the DB that this incident was a human call,
not a re-run of any automated step.

Usage:
    python -m src.apply_adjudication --db data/study.db --decisions ~/Downloads/adjudication_decisions.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3


def apply_decisions(db: sqlite3.Connection, decisions: list[dict]) -> dict:
    stats = {"accepted": 0, "rejected": 0, "skipped_unknown_incident": 0}
    for d in decisions:
        inc_id = d["incident_id"]
        verdict = d["verdict"]  # "accept" | "reject"
        row = db.execute("SELECT incident_id FROM incident WHERE incident_id=?", (inc_id,)).fetchone()
        if not row:
            stats["skipped_unknown_incident"] += 1
            continue
        if verdict == "accept":
            db.execute(
                "UPDATE incident SET eligible=1, index_make=?, exclusion_reason=NULL, "
                "coded_by='human_adjudication', coded_at=datetime('now') WHERE incident_id=?",
                (d.get("make") or None, inc_id))
            stats["accepted"] += 1
        elif verdict == "reject":
            db.execute(
                "UPDATE incident SET eligible=0, exclusion_reason=?, "
                "coded_by='human_adjudication', coded_at=datetime('now') WHERE incident_id=?",
                (d.get("reason") or "rejected in adjudication", inc_id))
            stats["rejected"] += 1
    db.commit()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--decisions", required=True)
    args = ap.parse_args()

    decisions = json.loads(open(args.decisions, encoding="utf-8").read())
    db = sqlite3.connect(args.db, timeout=60.0)
    db.execute("PRAGMA busy_timeout = 60000")
    stats = apply_decisions(db, decisions)
    db.close()
    print(stats)


if __name__ == "__main__":
    main()
