"""Export a random sample of eligible incidents, headline-blinded, for hand-coding a
gold standard (lean-track 8.2, `src/validate_coding.py`'s workflow step 1).

The whole point of a gold standard is that it's independent of the machine coding — so
this deliberately shows NONE of the LLM's suggested make, evidence quote, or notes, only
raw body text with headlines/standfirsts stripped (same safeguard as `llm_coding.py`).
All Tesla incidents are always included (there are too few to sample away), topped up
with a random non-Tesla sample to ~25-30 total per `validate_coding.py`'s own recommended
size.

Usage:
    python -m src.export_gold_sample --db data/study.db --out tools/gold_sample.json
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3

from .llm_coding import load_articles, strip_headlines


def pick_sample(db: sqlite3.Connection, *, n: int, seed: int) -> list[str]:
    db.row_factory = sqlite3.Row
    tesla = [r["incident_id"] for r in db.execute(
        "SELECT incident_id FROM incident WHERE eligible=1 AND index_make='Tesla'")]
    rest = [r["incident_id"] for r in db.execute(
        "SELECT incident_id FROM incident WHERE eligible=1 AND (index_make IS NULL OR index_make != 'Tesla')")]
    rng = random.Random(seed)
    rng.shuffle(rest)
    topup = max(0, n - len(tesla))
    return tesla + rest[:topup]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--out", default="tools/gold_sample.json")
    ap.add_argument("--n", type=int, default=28)
    ap.add_argument("--seed", type=int, default=20260825)
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    ids = pick_sample(db, n=args.n, seed=args.seed)

    out = []
    for inc_id in ids:
        articles = load_articles(db, inc_id)
        blinded = [
            {"outlet": a["outlet"],
             "body": strip_headlines(a.get("body", ""), a.get("headline", ""), a.get("standfirst", ""))}
            for a in articles
        ]
        out.append({"incident_id": inc_id, "articles": blinded})
    db.close()

    random.Random(args.seed).shuffle(out)  # blind order too — no clustering of Tesla cases together

    import pathlib
    outpath = pathlib.Path(args.out)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {len(out)} incident(s) to {outpath}")


if __name__ == "__main__":
    main()
