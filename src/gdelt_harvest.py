"""Brand-agnostic article harvest from the GDELT DOC 2.0 API (Protocol section 6.2).

Discovery must not depend on the brand, so this module imports the frozen query set,
which self-asserts brand-agnosticism at import time. There is no code path here that
accepts a user-supplied query.

Usage:
    python -m src.gdelt_harvest --start 2023-01-01 --end 2025-12-31 --db data/study.db
    python -m src.gdelt_harvest --dry-run          # show the plan, make no requests

Follows this repository's scraping rules: never stop on errors (log and continue),
>=2 second delay between requests, identify ourselves in the User-Agent.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import pathlib
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

from .queries import (GDELT_SOURCE_FILTER, gdelt_queries,  # asserts brand-agnosticism
                      gdelt_supplementary_queries)

LOG = logging.getLogger("gdelt_harvest")

API = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = (
    "tesla-headline-salience-study/0.2 "
    "(non-commercial media-content research; contact via repository)"
)
#: GDELT's own 429 response says "limit requests to one every 5 seconds"; 2.0s (this
#: repo's general scraping-rule minimum) is not enough for this host specifically. 6.0s
#: leaves a safety margin.
REQUEST_DELAY_S = 6.0
MAXRECORDS = 250             # GDELT hard cap per call
WINDOW_DAYS = 1              # daily windows keep every call under the 250 cap
#: Domain-restricted queries return a fraction of the volume, so they can span far
#: wider windows without approaching the cap — which keeps them cheap to add.
SUPPLEMENTARY_WINDOW_DAYS = 30

#: The top 10 Australian online news brands by readership (docs/OUTLETS.md).
#: Verified against real Ipsos iris "Top 10 News Category (excluding Weather &
#: Aggregators)" reports for March, May and June 2026 (averaged). Herald Sun and The Age
#: — both in the previous unverified list — do not appear in any of the three months and
#: have been dropped; SBS News and bbc.com are real, consistent top-10 entrants and have
#: been added. Daily Mail AUS's domain changed from dailymail.co.uk to dailymail.com
#: (noted on the Ipsos June 2026 report itself).
#:
#: Yahoo News Australia dropped 2026-08-25 (user decision, not an Ipsos ranking change):
#: its live sitemap only ever shows ~1 day of content, and Wayback had only 6 snapshots
#: of it across the entire 12-month study window (~1.7% day-coverage) — unlike
#: news.com.au's robots.txt gap, this isn't recoverable even manually, since the
#: historical state simply isn't stored anywhere. Existing Yahoo harvest rows were
#: deleted, not just excluded, so there's no ambiguity later about whether they count.
OUTLET_DOMAINS: dict[str, tuple[str, str, str]] = {
    # domain: (brand, ownership group, register)
    "news.com.au":      ("news.com.au", "News Corp", "tabloid"),
    "abc.net.au":       ("ABC News", "ABC", "public"),
    "9news.com.au":     ("9News", "Nine", "broadcast"),
    "nine.com.au":      ("9News", "Nine", "broadcast"),
    "dailymail.com":    ("Daily Mail Australia", "DMG Media", "tabloid"),
    "7news.com.au":     ("7NEWS", "Seven West", "broadcast"),
    "smh.com.au":       ("Sydney Morning Herald", "Nine", "broadsheet"),
    "theguardian.com":  ("The Guardian Australia", "Guardian", "broadsheet"),
    "sbs.com.au":       ("SBS News", "SBS", "public"),
    "bbc.com":          ("BBC", "BBC", "broadcast"),
}

#: Distinct brands in the frame. 9news/nine and the two Yahoo domains are one brand each,
#: so the domain count above exceeds this.
N_BRANDS = 10

#: Eligibility counts distinct BRANDS, not ownership groups (docs/OUTLETS.md § Threshold).
#: Nothing in the top 10 is excluded from the count: publishing wire copy under your own
#: masthead, headline included, is still an editorial decision. `outlet_group` is retained
#: so near-duplicate syndicated copy can still be identified.
NON_COUNTING_GROUPS: frozenset[str] = frozenset()


def canonical_url(url: str) -> str:
    """Strip tracking parameters and fragments so duplicates collapse (Codebook A6)."""
    p = urllib.parse.urlsplit(url)
    keep = [
        (k, v) for k, v in urllib.parse.parse_qsl(p.query)
        if not k.lower().startswith(("utm_", "fbclid", "gclid", "cmpid", "icid", "ito"))
    ]
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"),
                                    urllib.parse.urlencode(keep), ""))


def url_hash(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def match_outlet(url: str) -> tuple[str, str, str, str] | None:
    """(domain, brand, group, register) if the URL is one of the top 10 brands, else None.

    Daily Mail Australia (`dailymail.com`) and bbc.com share their domain with
    non-Australian editions, so URL alone cannot separate them. Every incident in this
    study is Australian by construction (clustering is anchored on Australian
    localities), so an article on either domain that clusters to an Australian incident
    is Australian coverage regardless of which desk wrote it. See `docs/OUTLETS.md` and
    `gdelt_supplementary_queries()`.
    """
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    for domain, (outlet, group, register) in OUTLET_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return domain, outlet, group, register
    return None


def _windows(start: dt.date, end: dt.date, days: int) -> list[tuple[dt.date, dt.date]]:
    out, cur = [], start
    while cur <= end:
        stop = min(cur + dt.timedelta(days=days - 1), end)
        out.append((cur, stop))
        cur = stop + dt.timedelta(days=1)
    return out


class GDELTResponseError(RuntimeError):
    """GDELT returned HTTP 200 with a non-JSON body (typically a plain-text error, e.g.
    a rate-limit notice or a query-syntax complaint). Must propagate as a failure, not be
    swallowed as "zero articles" — that would let a window be marked complete in
    `harvest_progress` despite the fetch having failed, silently losing coverage on any
    future resume.
    """


def _fetch(query: str, start: dt.date, end: dt.date, *, timeout: int = 60) -> list[dict]:
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(MAXRECORDS),
        "sort": "DateAsc",
        "startdatetime": start.strftime("%Y%m%d") + "000000",
        "enddatetime": end.strftime("%Y%m%d") + "235959",
    }
    req = urllib.request.Request(
        f"{API}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    if not raw.strip():
        return []
    try:
        return json.loads(raw).get("articles", [])
    except json.JSONDecodeError as exc:
        # GDELT returns plain-text errors with a 200 status often enough to matter (rate
        # limiting and query complaints both look like this). Raise rather than return
        # [] — see GDELTResponseError.
        raise GDELTResponseError(
            f"non-JSON response for {query!r} {start}..{end}: {raw[:200]}") from exc


def harvest(db: sqlite3.Connection, start: dt.date, end: dt.date,
            *, dry_run: bool = False, limit_queries: int | None = None,
            window_days: int = WINDOW_DAYS,
            supplementary: bool = True) -> dict[str, int]:
    # Two passes. The country-filtered queries need daily windows to stay under the
    # 250-record cap; the domain-targeted ones (which recover Daily Mail Australia and
    # anything else the country filter misses) return far less and run monthly, so
    # adding them costs a few hundred calls rather than doubling the harvest.
    passes: list[tuple[list[str], int]] = [
        (gdelt_queries()[:limit_queries], window_days)]
    if supplementary:
        passes.append((gdelt_supplementary_queries()[:limit_queries],
                       SUPPLEMENTARY_WINDOW_DAYS))

    plan = sum(len(qs) * len(_windows(start, end, wd)) for qs, wd in passes)
    for qs, wd in passes:
        LOG.info("  pass: %d queries x %d windows (%d-day)",
                 len(qs), len(_windows(start, end, wd)), wd)
    LOG.info("plan: %d calls total (~%.1f h at %.1fs/call)",
             plan, plan * REQUEST_DELAY_S / 3600, REQUEST_DELAY_S)
    stats = {"calls": 0, "returned": 0, "on_outlet_list": 0, "inserted": 0, "errors": 0,
             "capped_windows": 0, "skipped_done": 0}
    if dry_run:
        return stats

    done = {(r[0], r[1], r[2]) for r in db.execute(
        "SELECT query_hash, window_start, window_end FROM harvest_progress")}
    if done:
        LOG.info("resuming: %d (query, window) pairs already completed", len(done))

    for queries, wd in passes:
      windows = _windows(start, end, wd)
      for query in queries:
        qh = hashlib.sha1(query.encode()).hexdigest()[:12]
        for w_start, w_end in windows:
            key = (qh, w_start.isoformat(), w_end.isoformat())
            if key in done:
                stats["skipped_done"] += 1
                continue
            try:
                arts = _fetch(query, w_start, w_end)
            except (urllib.error.URLError, TimeoutError, OSError, GDELTResponseError) as exc:
                # Repository rule: never stop on errors, log and continue.
                LOG.warning("fetch failed %r %s..%s: %s", query, w_start, w_end, exc)
                stats["errors"] += 1
                time.sleep(REQUEST_DELAY_S)
                continue
            finally:
                stats["calls"] += 1

            stats["returned"] += len(arts)
            if len(arts) >= MAXRECORDS:
                # Silent truncation would bias coverage toward busy news days. Record it
                # so Phase 0 can shrink WINDOW_DAYS rather than losing articles unseen.
                LOG.warning("window hit the %d cap: %r %s..%s", MAXRECORDS, query, w_start, w_end)
                stats["capped_windows"] += 1

            rows = []
            for a in arts:
                url = canonical_url(a.get("url", ""))
                if not url:
                    continue
                m = match_outlet(url)
                if not m:
                    continue
                stats["on_outlet_list"] += 1
                rows.append((url_hash(url), url, "gdelt", m[0],
                             (a.get("title") or "").strip(), a.get("seendate"), query))
            if rows:
                cur = db.executemany(
                    "INSERT OR IGNORE INTO harvest "
                    "(url_hash, canonical_url, source, domain, title_at_crawl, seendate, query) "
                    "VALUES (?,?,?,?,?,?,?)", rows)
                stats["inserted"] += cur.rowcount

            # Checkpoint after the insert, in the same commit: a window is only marked
            # done once its articles are durably stored.
            db.execute("INSERT OR REPLACE INTO harvest_progress "
                       "(query_hash, window_start, window_end, n_returned, capped) "
                       "VALUES (?,?,?,?,?)",
                       (*key, len(arts), int(len(arts) >= MAXRECORDS)))
            db.commit()

            time.sleep(REQUEST_DELAY_S)
    return stats


def open_db(path: str | pathlib.Path) -> sqlite3.Connection:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Multiple harvesters/scripts run concurrently against the same file (WAL mode, one
    # writer at a time) — the 5s default timeout isn't enough under real contention and
    # surfaces as a hard crash ("database is locked") rather than a wait-and-retry.
    db = sqlite3.connect(path, timeout=60.0)
    db.execute("PRAGMA busy_timeout = 60000")
    schema = pathlib.Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    db.executescript(schema.read_text())
    return db


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-01-01")   # Protocol section 5
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--window-days", type=int, default=WINDOW_DAYS,
                    help="widen only if daily windows are demonstrably under the record cap")
    ap.add_argument("--limit-queries", type=int, default=None,
                    help="Phase 0 only: cap the query set for a feasibility probe")
    ap.add_argument("--no-supplementary", action="store_true",
                    help="skip the domain-targeted queries for Daily Mail / Guardian")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    db = open_db(args.db)
    stats = harvest(db, start, end, dry_run=args.dry_run,
                    limit_queries=args.limit_queries, window_days=args.window_days,
                    supplementary=not args.no_supplementary)
    LOG.info("harvest stats: %s", stats)
    LOG.info("harvest is resumable — re-running the same command skips completed windows")
    if stats["capped_windows"]:
        LOG.error("%d windows hit the result cap — reduce WINDOW_DAYS and re-run before "
                  "treating this harvest as complete", stats["capped_windows"])


if __name__ == "__main__":
    main()
