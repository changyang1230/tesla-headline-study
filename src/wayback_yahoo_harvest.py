"""Yahoo News Australia sitemap harvest via Wayback Machine snapshots.

Yahoo's LIVE sitemap (news-sitemap_articles_AU_en-AU.xml.gz) only ever shows roughly the
last 24 hours of articles (~600+ per day, not the ~30 days assumed before checking real
snapshot content — verified empirically 2026-08). Wayback has captured this URL roughly
monthly since 2022, so this harvester can only ever recover SPARSE, SCATTERED day-slices
of Yahoo's real 2023-2025 coverage (~1 real day sampled per month, not the full window).
This is a real, honest limitation — not a bug — and should be reported as such: Yahoo's
data here is partial-coverage evidence, not a reconstruction of Yahoo's full archive, and
should be weighted accordingly in any analysis (e.g. do not compute a per-outlet
proportion using this as the denominator the way daily-complete outlets like SMH allow).

Unlike other outlets, this sitemap is Google-News-style and gives the REAL headline
directly (`<news:title>`) and real publish date (`<news:publication_date>`) — no
slug-reconstruction needed, which is actually more reliable than the pseudo-title
approach used for other sitemap sources.

Usage:
    python -m src.wayback_yahoo_harvest --db data/study.db
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import time
import urllib.error
import urllib.request

from . import raw_cache
from .gdelt_harvest import canonical_url, match_outlet, open_db, url_hash
from .queries import keyword_regex
from .wayback_harvest import BACKOFFS, USER_AGENT

LOG = logging.getLogger("wayback_yahoo_harvest")

CDX_URL = ("https://web.archive.org/cdx/search/cdx"
           "?url=https%3A%2F%2Fau.news.yahoo.com%2Fsitemaps%2F"
           "news-sitemap_articles_AU_en-AU.xml.gz&output=json&limit=200")
TAG = "wayback:au.news.yahoo.com"
SOURCE = "sitemap"

_URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.DOTALL)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_TITLE_RE = re.compile(r"<news:title>([^<]+)</news:title>")
_PUBDATE_RE = re.compile(r"<news:publication_date>([^<]+)</news:publication_date>")


def _fetch(url: str, *, timeout: int = 60) -> bytes | None:
    cached = raw_cache.get("wayback_yahoo", url)
    if cached is not None:
        return cached
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt, backoff in enumerate(BACKOFFS):
        if backoff:
            LOG.info("retry %d/%d after %ds", attempt, len(BACKOFFS) - 1, backoff)
            time.sleep(backoff)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            raw_cache.put("wayback_yahoo", url, raw)
            return raw
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                continue
            if exc.code in (403, 404):
                return None
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
    return None


def list_snapshots(*, start: str = "20230101", end: str = "20251231") -> list[tuple[str, str]]:
    """Returns (timestamp, original_url) pairs from CDX, filtered to the study window."""
    raw = _fetch(CDX_URL)
    if not raw:
        return []
    import json
    rows = json.loads(raw.decode("utf-8"))[1:]  # drop the header row
    # CDX columns: urlkey, timestamp, original, mimetype, statuscode, digest, length
    return [(r[1], r[2]) for r in rows if start <= r[1][:8] <= end]


def harvest(db: sqlite3.Connection, *, start: str = "20230101", end: str = "20251231",
            dry_run: bool = False) -> dict[str, int]:
    kw = keyword_regex()
    snapshots = list_snapshots(start=start, end=end)
    LOG.info("plan: %d Wayback snapshots of Yahoo's sitemap (sparse day-coverage, "
             "not comprehensive — see module docstring)", len(snapshots))
    stats = {"snapshots": 0, "urls_seen": 0, "candidates": 0, "inserted": 0, "errors": 0,
              "skipped_done": 0}
    if dry_run or not snapshots:
        return stats

    done = {r[0] for r in db.execute(
        "SELECT window_start FROM harvest_progress WHERE query_hash = ?", (TAG,))}
    if done:
        LOG.info("resuming: %d snapshots already completed", len(done))

    for ts, orig in snapshots:
        key = ts
        if key in done:
            stats["skipped_done"] += 1
            continue
        wb_url = f"https://web.archive.org/web/{ts}if_/{orig}"
        raw = _fetch(wb_url)
        if raw is None:
            stats["errors"] += 1
        else:
            import gzip
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", errors="replace")

            rows = []
            for block in _URL_BLOCK_RE.findall(text):
                loc_m, title_m, date_m = _LOC_RE.search(block), _TITLE_RE.search(block), _PUBDATE_RE.search(block)
                if not (loc_m and title_m):
                    continue
                stats["urls_seen"] += 1
                title = title_m.group(1)
                if not kw.search(title):
                    continue
                stats["candidates"] += 1
                cu = canonical_url(loc_m.group(1))
                m = match_outlet(cu) if cu else None
                if not m:
                    continue
                seendate = date_m.group(1)[:10] if date_m else ts[:4] + "-" + ts[4:6] + "-" + ts[6:8]
                rows.append((url_hash(cu), cu, SOURCE, m[0], title, seendate, TAG))
            if rows:
                cur = db.executemany(
                    "INSERT OR IGNORE INTO harvest "
                    "(url_hash, canonical_url, source, domain, title_at_crawl, seendate, query) "
                    "VALUES (?,?,?,?,?,?,?)", rows)
                stats["inserted"] += cur.rowcount

        db.execute("INSERT OR REPLACE INTO harvest_progress "
                   "(query_hash, window_start, window_end, n_returned, capped) "
                   "VALUES (?,?,?,?,?)", (TAG, key, key, 0, 0))
        db.commit()
        stats["snapshots"] += 1
        time.sleep(4.0)

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                         format="%(asctime)s %(levelname)-7s %(message)s")

    db = open_db(args.db)
    stats = harvest(db, start=args.start.replace("-", ""), end=args.end.replace("-", ""),
                     dry_run=args.dry_run)
    LOG.info("done: %s", stats)


if __name__ == "__main__":
    main()
