"""Turn verified incidents plus fetched articles into the locked analysis dataset.

Applies the frozen lexicon to produce the automated outcomes (Protocol section 8.1), runs
near-duplicate detection for syndication (section 8.4), and records provenance hashes so
the dataset can be traced to the exact lexicon and query set that produced it.

Body text is read from `data/bodies/<article_id>.txt` if present — those files stay on
disk and are never committed (Protocol section 8.5).

Usage:
    python -m src.build_dataset --db data/study.db
    python -m src.build_dataset --db data/study.db --export output/analysis_dataset.csv
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import logging
import math
import pathlib
import sqlite3

from .cluster_incidents import cosine, _tfidf, tokenise
from .lexicon import canonical_make, names_make

LOG = logging.getLogger("build_dataset")

SYNDICATION_COSINE = 0.85     # Protocol section 8.4
BODY_DIR = pathlib.Path("data/bodies")


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def record_provenance(db: sqlite3.Connection) -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    for key, rel in (("lexicon_sha", "src/lexicon.py"),
                     ("queries_sha", "src/queries.py"),
                     ("protocol_sha", "PROTOCOL.md"),
                     ("codebook_sha", "CODEBOOK.md")):
        f = root / rel
        if f.exists():
            db.execute("INSERT OR REPLACE INTO provenance (key, value) VALUES (?, ?)",
                       (key, _sha(f)))
    db.commit()


def body_text(article_id: str) -> str:
    f = BODY_DIR / f"{article_id}.txt"
    return f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""


def code_outcomes(db: sqlite3.Connection) -> dict[str, int]:
    """Automated primary and secondary outcomes for every article with an incident."""
    db.row_factory = sqlite3.Row
    rows = list(db.execute("""
        SELECT a.article_id, a.headline, a.standfirst,
               i.index_make, i.second_make
        FROM article a JOIN incident i ON i.incident_id = a.incident_id
        WHERE i.index_make IS NOT NULL AND i.index_make != ''
    """))
    stats = collections.Counter()
    for r in rows:
        make = canonical_make(r["index_make"]) or r["index_make"]
        headline = r["headline"] or ""
        standfirst = r["standfirst"] or ""
        body = body_text(r["article_id"])

        head = int(names_make(headline, make))
        strict = int(names_make(headline, make, strict=True))
        second = (canonical_make(r["second_make"]) or r["second_make"]) if r["second_make"] else None
        head2 = int(names_make(headline, second)) if second else None
        in_body = int(names_make(body, make)) if body else None

        if head:
            pos = "headline"
        elif standfirst and names_make(standfirst, make):
            pos = "standfirst"
        elif body:
            paras = [p for p in body.split("\n") if p.strip()]
            if paras and names_make(paras[0], make):
                pos = "first_paragraph"
            elif in_body:
                pos = "later_body"
            else:
                pos = "absent"
        else:
            pos = None  # body not available; leave for human coding

        db.execute("""UPDATE article SET headline_names_make=?, headline_names_make_strict=?,
                      headline_names_second_make=?, body_names_make=?,
                      first_mention_position=?, coded_at=datetime('now')
                      WHERE article_id=?""",
                   (head, strict, head2, in_body, pos, r["article_id"]))
        stats["coded"] += 1
        stats["headline_hits"] += head
        stats["no_body_text"] += int(not body)
    db.commit()
    return dict(stats)


def detect_syndication(db: sqlite3.Connection) -> int:
    """Flag near-duplicate articles within each incident (Protocol section 8.4).

    Wire copy republished under eight mastheads is one piece of editorial judgment, not
    eight. Without this the primary analysis would treat it as eight independent
    observations and overstate precision.
    """
    db.row_factory = sqlite3.Row
    flagged = 0
    incidents = [r[0] for r in db.execute(
        "SELECT DISTINCT incident_id FROM article WHERE incident_id IS NOT NULL")]
    for inc in incidents:
        arts = list(db.execute(
            "SELECT article_id FROM article WHERE incident_id=? ORDER BY publish_datetime", (inc,)))
        ids = [a["article_id"] for a in arts]
        docs = [tokenise(body_text(i)) for i in ids]
        if not any(docs):
            continue
        vecs, _, _ = _tfidf(docs)
        parent: dict[str, str] = {}
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                if docs[a] and docs[b] and cosine(vecs[a], vecs[b]) >= SYNDICATION_COSINE:
                    parent.setdefault(ids[b], parent.get(ids[a], ids[a]))
        for child, root in parent.items():
            db.execute("UPDATE article SET syndication_group_id=? WHERE article_id IN (?,?)",
                       (f"S-{inc}-{root[:8]}", child, root))
            flagged += 1
    db.commit()
    return flagged


def export(db: sqlite3.Connection, path: str) -> int:
    db.row_factory = sqlite3.Row
    rows = list(db.execute("SELECT * FROM v_analysis"))
    if not rows:
        LOG.warning("v_analysis is empty — no eligible incidents with articles yet")
        return 0
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--export", default=None)
    ap.add_argument("--skip-syndication", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    db = sqlite3.connect(args.db)
    record_provenance(db)
    LOG.info("outcome coding: %s", code_outcomes(db))
    if not args.skip_syndication:
        LOG.info("syndication: %d articles grouped", detect_syndication(db))
    if args.export:
        LOG.info("exported %d rows to %s", export(db, args.export), args.export)
    LOG.info("provenance: %s", dict(db.execute("SELECT key, value FROM provenance")))


if __name__ == "__main__":
    main()
