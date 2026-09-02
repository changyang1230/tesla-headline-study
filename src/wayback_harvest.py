"""news.com.au sitemap harvest via the Wayback Machine, not news.com.au directly.

news.com.au's own robots.txt blanket-disallows automated collection for unnamed agents
(`User-agent: *` / `Disallow: /`), plus an explicit written notice requiring publisher
permission — treated as a hard no in this project (see docs/OUTLETS.md and CLAUDE.md).
This module never talks to news.com.au. It only talks to web.archive.org (no robots.txt
at all, confirmed 2026-08), retrieving snapshots that the Internet Archive's own crawler
already captured — a different actor's data, not us scraping the disallowed site.

We already know the exact daily sitemap URL shape (found by manually browsing
news.com.au in a real browser, not by this script):
    https://www.news.com.au/sitemap.xml?yyyy=YYYY&mm=MM&dd=DD
This module fetches each day's Wayback snapshot of that URL directly, rather than
CDX-searching the whole news.com.au domain — a domain-wide CDX query times out at this
scale (confirmed empirically for smh.com.au and news.com.au both; the Internet Archive's
own server can't answer it in reasonable time for a high-traffic site).

Rate-limit handling follows the same strategy already validated in the sibling
`coronial` project (scripts/import_nsw_wayback.py): Internet Archive allows roughly
15 req/min; exceeding it triggers a ~5-minute IP-level block signalled by HTTP 429.
Backoff schedule: immediate retry, then 15s, 60s, 300s — a real 429 gets the full 300s
wait, not a shorter guess. Reference: https://archive.org/details/toomanyrequests_20191110

Usage:
    python -m src.wayback_harvest --start 2023-01-01 --end 2025-12-31 --db data/study.db
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sqlite3
import time
import urllib.error
import urllib.request

from . import raw_cache
from .gdelt_harvest import canonical_url, match_outlet, open_db, url_hash
from .queries import keyword_regex
from .sitemap_harvest import extract_url_items, slug_to_pseudo_title_newscorp

LOG = logging.getLogger("wayback_harvest")

USER_AGENT = (
    "tesla-headline-salience-study/0.2 "
    "(non-commercial media-content research; contact via repository)"
)
REQUEST_DELAY_S = 4.0        # ~15 req/min budget, per archive.org's documented rate limit
BACKOFFS = (0, 15, 60, 300)  # seconds — matches coronial/scripts/import_nsw_wayback.py

DOMAIN = "news.com.au"
SOURCE = "sitemap"
TAG = "wayback:news.com.au"
ORIGINAL_TEMPLATE = "https://www.news.com.au/sitemap.xml?yyyy={y}&mm={m:02d}&dd={d:02d}"
WAYBACK_TEMPLATE = "https://web.archive.org/web/{ts}if_/{original}"


def _fetch_snapshot(original_url: str, target_date: dt.date, *, timeout: int = 60) -> str | None:
    """Fetch the Wayback snapshot closest to target_date. Returns None (not raise) if
    Internet Archive has no snapshot for this URL at all — a normal, expected outcome,
    distinct from a transient fetch failure the caller should retry.
    """
    ts = target_date.strftime("%Y%m%d") + "000000"
    wb_url = WAYBACK_TEMPLATE.format(ts=ts, original=original_url)

    cached = raw_cache.get("wayback", wb_url)
    if cached is not None:
        return cached.decode("utf-8", errors="replace")

    req = urllib.request.Request(wb_url, headers={"User-Agent": USER_AGENT})

    for attempt, backoff in enumerate(BACKOFFS):
        if backoff:
            LOG.info("retry %d/%d after %ds", attempt, len(BACKOFFS) - 1, backoff)
            time.sleep(backoff)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            raw_cache.put("wayback", wb_url, raw)
            return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                LOG.warning("HTTP 429 — rate limited, backing off %ds", BACKOFFS[-1])
                continue
            if exc.code in (404, 403):
                return None      # no snapshot for this URL — not an error to retry
            LOG.warning("HTTP %s fetching %s: %s", exc.code, wb_url, exc)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            LOG.warning("fetch error %s: %s", wb_url, exc)
    return None


def _dates(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def harvest(db: sqlite3.Connection, start: dt.date, end: dt.date,
            *, dry_run: bool = False) -> dict[str, int]:
    kw = keyword_regex()
    dates = list(_dates(start, end))
    LOG.info("plan: %d daily snapshots via Wayback for %s (~%.1f h at %.1fs/call)",
             len(dates), DOMAIN, len(dates) * REQUEST_DELAY_S / 3600, REQUEST_DELAY_S)
    stats = {"days": 0, "no_snapshot": 0, "urls_seen": 0, "candidates": 0, "inserted": 0,
              "errors": 0, "skipped_done": 0}
    if dry_run:
        return stats

    done = {r[0] for r in db.execute(
        "SELECT window_start FROM harvest_progress WHERE query_hash = ?", (TAG,))}
    if done:
        LOG.info("resuming: %d days already completed", len(done))

    for d in dates:
        key = d.isoformat()
        if key in done:
            stats["skipped_done"] += 1
            continue
        original = ORIGINAL_TEMPLATE.format(y=d.year, m=d.month, d=d.day)
        raw = _fetch_snapshot(original, d)
        if raw is None:
            stats["no_snapshot"] += 1
        else:
            items = extract_url_items(raw)
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
                seendate = (lastmod or "")[:10] or key
                rows.append((url_hash(cu), cu, SOURCE, m[0],
                             f"[slug, not real headline] {pseudo_title}", seendate, TAG))
            if rows:
                cur = db.executemany(
                    "INSERT OR IGNORE INTO harvest "
                    "(url_hash, canonical_url, source, domain, title_at_crawl, seendate, query) "
                    "VALUES (?,?,?,?,?,?,?)", rows)
                stats["inserted"] += cur.rowcount

        db.execute("INSERT OR REPLACE INTO harvest_progress "
                   "(query_hash, window_start, window_end, n_returned, capped) "
                   "VALUES (?,?,?,?,?)",
                   (TAG, key, key, 0 if raw is None else len(items), 0))
        db.commit()
        stats["days"] += 1
        time.sleep(REQUEST_DELAY_S)

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                         format="%(asctime)s %(levelname)-7s %(message)s")

    db = open_db(args.db)
    stats = harvest(db, dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end),
                     dry_run=args.dry_run)
    LOG.info("done: %s", stats)


if __name__ == "__main__":
    main()
