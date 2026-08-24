"""Brand-agnostic article harvest from the GDELT DOC 2.0 API (Protocol section 6.2).

Discovery must not depend on the brand, so this module imports the frozen query set,
which self-asserts brand-agnosticism at import time. There is no code path here that
accepts a user-supplied query.

Usage:
    python -m src.gdelt_harvest --start 2021-01-01 --end 2025-12-31 --db data/study.db
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

from .queries import GDELT_SOURCE_FILTER, gdelt_queries  # asserts brand-agnosticism on import

LOG = logging.getLogger("gdelt_harvest")

API = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = (
    "coronial-research/tesla-headline-salience "
    "(academic media-content study; contact via repository)"
)
REQUEST_DELAY_S = 2.0        # repository rule
MAXRECORDS = 250             # GDELT hard cap per call
WINDOW_DAYS = 1              # daily windows keep every call under the 250 cap

#: Domains from docs/OUTLETS.md. Kept here so the harvester can filter server results
#: without parsing markdown; docs/OUTLETS.md remains the human-readable source of truth
#: and tests assert the two agree.
OUTLET_DOMAINS: dict[str, tuple[str, str, str]] = {
    # domain: (outlet, group, register)
    "news.com.au":            ("news.com.au", "News Corp", "tabloid"),
    "theaustralian.com.au":   ("The Australian", "News Corp", "broadsheet"),
    "heraldsun.com.au":       ("Herald Sun", "News Corp", "tabloid"),
    "dailytelegraph.com.au":  ("Daily Telegraph", "News Corp", "tabloid"),
    "couriermail.com.au":     ("Courier-Mail", "News Corp", "tabloid"),
    "adelaidenow.com.au":     ("The Advertiser", "News Corp", "tabloid"),
    "ntnews.com.au":          ("NT News", "News Corp", "tabloid"),
    "themercury.com.au":      ("The Mercury", "News Corp", "tabloid"),
    "skynews.com.au":         ("Sky News Australia", "News Corp", "broadcast"),
    "smh.com.au":             ("Sydney Morning Herald", "Nine", "broadsheet"),
    "theage.com.au":          ("The Age", "Nine", "broadsheet"),
    "brisbanetimes.com.au":   ("Brisbane Times", "Nine", "broadsheet"),
    "watoday.com.au":         ("WAtoday", "Nine", "broadsheet"),
    "9news.com.au":           ("9News", "Nine", "broadcast"),
    "afr.com":                ("Australian Financial Review", "Nine", "broadsheet"),
    "7news.com.au":           ("7NEWS", "Seven West", "broadcast"),
    "thewest.com.au":         ("The West Australian", "Seven West", "tabloid"),
    "perthnow.com.au":        ("PerthNow", "Seven West", "tabloid"),
    "abc.net.au":             ("ABC News", "ABC", "public"),
    "sbs.com.au":             ("SBS News", "SBS", "public"),
    "theguardian.com":        ("The Guardian Australia", "Guardian", "broadsheet"),
    "10play.com.au":          ("10 News", "Paramount", "broadcast"),
    "canberratimes.com.au":   ("The Canberra Times", "ACM", "broadsheet"),
    "newcastleherald.com.au": ("Newcastle Herald", "ACM", "tabloid"),
    "examiner.com.au":        ("The Examiner", "ACM", "tabloid"),
    "bordermail.com.au":      ("The Border Mail", "ACM", "tabloid"),
    "bendigoadvertiser.com.au": ("Bendigo Advertiser", "ACM", "tabloid"),
    "illawarramercury.com.au": ("Illawarra Mercury", "ACM", "tabloid"),
    "thenewdaily.com.au":     ("The New Daily", "independent", "broadsheet"),
    "crikey.com.au":          ("Crikey", "Private Media", "broadsheet"),
    "aap.com.au":             ("AAP", "AAP", "wire"),
    "au.yahoo.com":           ("Yahoo News Australia", "Yahoo", "aggregator"),
}

#: Outlet groups that do not count toward the ">=3 distinct outlet groups" eligibility
#: threshold, because they carry other outlets' copy (Protocol section 6.4).
NON_COUNTING_GROUPS = frozenset({"AAP", "Yahoo"})


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
    """(domain, outlet, group, register) if the URL is on the outlet list, else None."""
    host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
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
    except json.JSONDecodeError:
        # GDELT returns plain-text errors with a 200 status often enough to matter.
        LOG.warning("non-JSON response for %r %s..%s: %s", query, start, end, raw[:200])
        return []


def harvest(db: sqlite3.Connection, start: dt.date, end: dt.date,
            *, dry_run: bool = False, limit_queries: int | None = None,
            window_days: int = WINDOW_DAYS) -> dict[str, int]:
    queries = gdelt_queries()[:limit_queries]
    windows = _windows(start, end, window_days)
    plan = len(queries) * len(windows)
    LOG.info("plan: %d queries x %d windows = %d calls (~%.1f h at %.1fs/call)",
             len(queries), len(windows), plan, plan * REQUEST_DELAY_S / 3600, REQUEST_DELAY_S)
    stats = {"calls": 0, "returned": 0, "on_outlet_list": 0, "inserted": 0, "errors": 0,
             "capped_windows": 0, "skipped_done": 0}
    if dry_run:
        return stats

    done = {(r[0], r[1], r[2]) for r in db.execute(
        "SELECT query_hash, window_start, window_end FROM harvest_progress")}
    if done:
        LOG.info("resuming: %d (query, window) pairs already completed", len(done))

    for query in queries:
        qh = hashlib.sha1(query.encode()).hexdigest()[:12]
        for w_start, w_end in windows:
            key = (qh, w_start.isoformat(), w_end.isoformat())
            if key in done:
                stats["skipped_done"] += 1
                continue
            try:
                arts = _fetch(query, w_start, w_end)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
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
    db = sqlite3.connect(path)
    schema = pathlib.Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    db.executescript(schema.read_text())
    return db


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--window-days", type=int, default=WINDOW_DAYS,
                    help="widen only if daily windows are demonstrably under the record cap")
    ap.add_argument("--limit-queries", type=int, default=None,
                    help="Phase 0 only: cap the query set for a feasibility probe")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    db = open_db(args.db)
    stats = harvest(db, start, end, dry_run=args.dry_run,
                    limit_queries=args.limit_queries, window_days=args.window_days)
    LOG.info("harvest stats: %s", stats)
    LOG.info("harvest is resumable — re-running the same command skips completed windows")
    if stats["capped_windows"]:
        LOG.error("%d windows hit the result cap — reduce WINDOW_DAYS and re-run before "
                  "treating this harvest as complete", stats["capped_windows"])


if __name__ == "__main__":
    main()
