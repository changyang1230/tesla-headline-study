"""Import manually-saved news.com.au sitemap XML files into the harvest table.

news.com.au's robots.txt blanket-disallows automated collection (see docs/OUTLETS.md) —
the daily sitemap pages that Wayback never snapshotted (~57% of the 2025-09/2026-08
window) were instead fetched by the investigator personally, in a browser, and saved to
disk. This module only ever reads already-saved local files; it makes no network
requests and touches no automated-access question at all.

Expects filenames of the form `sitemap<YYMMDD>.xml` (the browser's default download name
for `news.com.au/sitemap.xml?yyyy=..&mm=..&dd=..`) in the given directory. The date comes
from the filename, not from parsing every article's own lastmod, since a query for a
specific day may include lastmod timestamps from neighbouring days (same caveat as
sitemap_harvest.py's other daily sources).

Usage:
    python -m src.manual_sitemap_import --dir "/path/to/news.com.au xml" --db data/study.db
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import pathlib
import re
import sqlite3

from .gdelt_harvest import canonical_url, match_outlet, open_db, url_hash
from .queries import keyword_regex
from .sitemap_harvest import extract_url_items, slug_to_pseudo_title_newscorp

LOG = logging.getLogger("manual_sitemap_import")

SOURCE = "sitemap"
TAG = "manual:news.com.au"
_FILENAME_RE = re.compile(r"sitemap(\d{6})\.xml$", re.IGNORECASE)


def date_from_filename(path: pathlib.Path) -> dt.date | None:
    m = _FILENAME_RE.search(path.name)
    if not m:
        return None
    yy, mm, dd = m.group(1)[0:2], m.group(1)[2:4], m.group(1)[4:6]
    return dt.date(2000 + int(yy), int(mm), int(dd))


def import_dir(db: sqlite3.Connection, directory: pathlib.Path) -> dict[str, int]:
    kw = keyword_regex()
    stats = {"files": 0, "skipped_no_date": 0, "urls_seen": 0, "candidates": 0, "inserted": 0}

    for path in sorted(directory.glob("*.xml")):
        date = date_from_filename(path)
        if not date:
            LOG.warning("%s: couldn't parse a date from the filename, skipping", path.name)
            stats["skipped_no_date"] += 1
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        items = extract_url_items(text)
        stats["urls_seen"] += len(items)

        rows = []
        for loc, lastmod in items:
            pseudo_title = slug_to_pseudo_title_newscorp(loc)
            if not pseudo_title or not kw.search(pseudo_title):
                continue
            stats["candidates"] += 1
            cu = canonical_url(loc)
            m = match_outlet(cu) if cu else None
            if not m:
                continue
            seendate = (lastmod or "")[:10] or date.isoformat()
            rows.append((url_hash(cu), cu, SOURCE, m[0],
                         f"[slug, not real headline] {pseudo_title}", seendate, TAG))
        if rows:
            cur = db.executemany(
                "INSERT OR IGNORE INTO harvest "
                "(url_hash, canonical_url, source, domain, title_at_crawl, seendate, query) "
                "VALUES (?,?,?,?,?,?,?)", rows)
            stats["inserted"] += cur.rowcount
        db.commit()
        stats["files"] += 1

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True, help="directory of manually-saved sitemap*.xml files")
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                         format="%(asctime)s %(levelname)-7s %(message)s")

    directory = pathlib.Path(args.dir)
    if not directory.is_dir():
        raise SystemExit(f"not a directory: {directory}")

    db = open_db(args.db)
    stats = import_dir(db, directory)
    LOG.info("done: %s", stats)


if __name__ == "__main__":
    main()
