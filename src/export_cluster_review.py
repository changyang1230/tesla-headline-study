"""Export every eligible incident and its articles for manual cluster-correctness review
— a distinct check from `export_adjudication.py`'s incident-level accept/reject: this
asks "does *this specific article* actually belong in *this* incident's cluster?", not
"is this incident real / is the suggested make correct?"

Clustering is text-similarity-based (`cluster_incidents.py`) and has already been caught
mis-grouping unrelated stories at least twice (see CLAUDE.md's "Real bugs found" section
— a helicopter crash merged into a cyclist-strike incident, an e-bike fatality merged
into a car/ute crash). Both were caught incidentally, via the LLM coder's own notes. This
export exists to let a human deliberately sweep every one of the 167 eligible incidents'
articles for the same failure mode, rather than relying on it surfacing by accident.

Usage:
    python -m src.export_cluster_review --db data/study.db --out tools/cluster_review_data.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3


def load_eligible(db: sqlite3.Connection) -> list[dict]:
    db.row_factory = sqlite3.Row
    incidents = []
    for inc in db.execute(
            "SELECT incident_id, incident_date, index_make FROM incident "
            "WHERE eligible=1 ORDER BY incident_date"):
        articles = [dict(r) for r in db.execute(
            "SELECT article_id, outlet, headline, url, headline_names_make FROM article "
            "WHERE incident_id=? AND excluded=0 ORDER BY publish_datetime",
            (inc["incident_id"],))]
        make = inc["index_make"] or "(not established)"
        incidents.append({
            "incident_id": inc["incident_id"],
            "incident_date": inc["incident_date"],
            "make": make,
            "is_tesla": make == "Tesla",
            "n_outlets": len({a["outlet"] for a in articles}),
            "articles": articles,
        })
    return incidents


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--out", default="tools/cluster_review_data.json")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    incidents = load_eligible(db)
    db.close()

    import pathlib
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(incidents, indent=1), encoding="utf-8")
    n_articles = sum(len(i["articles"]) for i in incidents)
    print(f"wrote {len(incidents)} incident(s), {n_articles} article(s) to {out}")


if __name__ == "__main__":
    main()
