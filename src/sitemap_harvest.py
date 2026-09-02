"""Direct-outlet sitemap harvest — a third discovery source alongside GDELT/CC-NEWS
(Protocol section 6.2), used when GDELT is unavailable or an outlet's own coverage is
worth cross-checking.

Unlike GDELT/CC-NEWS, there is no server-side keyword search: a sitemap lists every URL
an outlet published, brand-agnostic by construction. Candidate filtering happens locally
with `queries.keyword_regex()`, applied to a pseudo-headline recovered from the URL slug
(outlets embed the headline in the URL, hyphenated). This pseudo-title is good enough to
prioritise a URL as a candidate incident but is NOT the real headline —
`headline_names_make` and any outcome coding must come from the actual rendered article
page, fetched separately. `title_at_crawl` here is marked accordingly.

Two sitemap shapes are handled:
- "daily": one sitemap file per calendar day (SMH, Nine) — iterate the date range.
- "paginated": a fixed set of numbered files covering the outlet's whole history in no
  particular order (ABC) — fetch every page once, filter candidates by the date embedded
  in the URL path.

Checked and NOT usable this way: news.com.au (News Corp) has a blanket
`Disallow: /` in robots.txt for unnamed agents plus an explicit automated-collection
notice — treated as a hard no, not a technical obstacle. The Guardian's public sitemap is
Google-News-style and only covers a rolling ~2 days. See docs/OUTLETS.md.

Note: ABC's and Nine's robots.txt explicitly disallow named Claude/Anthropic crawlers
(`ClaudeBot`, `Claude-Web`, `anthropic-ai`, `claudebot`) while allowing `User-agent: *`
generally. This harvester identifies itself with a distinct, honest User-Agent string
naming the study and a contact point, not as one of those named bots — a deliberate
choice, discussed with the study's investigator, not an oversight.

Usage:
    python -m src.sitemap_harvest --domain smh.com.au --start 2023-01-01 --end 2025-12-31 --db data/study.db
    python -m src.sitemap_harvest --domain abc.net.au --db data/study.db
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import logging
import re
import sqlite3
import time
import urllib.error
import urllib.request

from . import raw_cache
from .gdelt_harvest import canonical_url, match_outlet, open_db, url_hash
from .queries import keyword_regex

LOG = logging.getLogger("sitemap_harvest")

USER_AGENT = (
    "tesla-headline-salience-study/0.2 "
    "(non-commercial media-content research; contact via repository)"
)
REQUEST_DELAY_S = 2.0        # this repository's baseline politeness rule (own server, not a rate-limited API)

#: source label distinguishes this from GDELT/CC-NEWS in `harvest.source` and flags the
#: title as slug-derived, not the real rendered headline.
SOURCE = "sitemap"

_URL_RE = re.compile(r"<loc>([^<]+)</loc>")
_URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.DOTALL)
_LASTMOD_RE = re.compile(r"<lastmod>([^<]+)</lastmod>")
_TRAILING_SLUG_RE = re.compile(r"/([a-z0-9][a-z0-9-]{5,})(?:\.html)?/?$", re.IGNORECASE)
_ABC_PATH_RE = re.compile(r"/news/(\d{4}-\d{2}-\d{2})/([^/]+)/(\d+)$")
_STORY_ID_SUFFIX_RE = re.compile(r"-\d{8}-p[a-z0-9]+$", re.IGNORECASE)
_SEVEN_NEWS_ID_SUFFIX_RE = re.compile(r"-c-\d+$", re.IGNORECASE)
_SBS_PATH_RE = re.compile(r"/article/([^/]+)/[a-z0-9]+/?$", re.IGNORECASE)


def slug_to_pseudo_title_trailing(url: str) -> str:
    """SMH/Nine style: '.../some-headline-slug-20240101-p5eugr.html' -> 'some headline slug'."""
    m = _TRAILING_SLUG_RE.search(url.split("?")[0])
    if not m:
        return ""
    slug = _STORY_ID_SUFFIX_RE.sub("", m.group(1))
    return slug.replace("-", " ")


def slug_to_pseudo_title_abc(url: str) -> str:
    """ABC style: '.../news/2026-07-27/act-dash-cam-footage-.../106963942' -> the middle segment.

    Many ABC URLs have a generic filler slug ('abc-news', 'video-of-...') for video/short
    clips with no real headline; those simply won't match the crash vocabulary and are
    dropped naturally, same as any other non-matching article.
    """
    m = _ABC_PATH_RE.search(url.split("?")[0])
    if not m:
        return ""
    return m.group(2).replace("-", " ")


def abc_url_date(url: str) -> str | None:
    m = _ABC_PATH_RE.search(url.split("?")[0])
    return m.group(1) if m else None


def slug_to_pseudo_title_seven(url: str) -> str:
    """7NEWS style: '.../two-time-grand-slam-champion-...-c-13078812' -> the slug, no id."""
    m = _TRAILING_SLUG_RE.search(url.split("?")[0])
    if not m:
        return ""
    slug = _SEVEN_NEWS_ID_SUFFIX_RE.sub("", m.group(1))
    return slug.replace("-", " ")


def slug_to_pseudo_title_sbs(url: str) -> str:
    """SBS style: '.../news/article/rebecca-was-just-15-when.../2kmhnqb05' -> the slug."""
    m = _SBS_PATH_RE.search(url.split("?")[0])
    if not m:
        return ""
    return m.group(1).replace("-", " ")


_NEWSCORP_PATH_RE = re.compile(r"/([^/]+)/news-story/[a-f0-9]+/?$", re.IGNORECASE)


def slug_to_pseudo_title_newscorp(url: str) -> str:
    """News Corp style: '.../multiple-deaths-in-us-new-year-.../news-story/159d083e...' ->
    the slug (NOT the trailing hex story id, which slug_to_pseudo_title_trailing would
    wrongly grab)."""
    m = _NEWSCORP_PATH_RE.search(url.split("?")[0])
    if not m:
        return ""
    return m.group(1).replace("-", " ")


#: domain -> config.
#:   "daily"          — one file per calendar day, iterate the date range (SMH, Nine, Daily Mail).
#:   "paginated"       — a fixed, unordered set of numbered files covering the outlet's
#:                        whole history; fetch every page once, filter by embedded date (ABC).
#:   "index_list"      — a top-level index enumerates dated sub-files explicitly; fetch the
#:                        index once, then only the sub-files whose path falls in range (7NEWS).
#:   "monthly_index"   — like "daily" but one file per calendar month (SBS).
SITE_CONFIGS: dict[str, dict] = {
    "smh.com.au": {
        "kind": "daily",
        "template": "https://www.smh.com.au/sitemaps/smh-articles-{date}.xml",
        "slug_fn": slug_to_pseudo_title_trailing,
    },
    "nine.com.au": {
        "kind": "daily",
        "template": "https://www.nine.com.au/sitemaps/nine-articles-{date}.xml",
        "slug_fn": slug_to_pseudo_title_trailing,
    },
    "abc.net.au": {
        "kind": "paginated",
        "template": "https://www.abc.net.au/sitemaps/sitemap-news-{page}.xml.gz",
        "max_pages": 30,        # probed 2026-08: valid pages are 0-12; scan a margin above that
        "slug_fn": slug_to_pseudo_title_abc,
        "date_fn": abc_url_date,
        "gzipped": True,
    },
    "dailymail.com": {
        "kind": "daily",
        "template": "https://www.dailymail.com/sitemap-articles-day~{date}.xml",
        "date_fmt": "%Y-%m-%d",     # unlike SMH/Nine's YYYYMMDD, this host uses YYYY-MM-DD
        "slug_fn": slug_to_pseudo_title_trailing,
    },
    "7news.com.au": {
        "kind": "index_list",
        "index_url": "https://www.7news.com.au/sitemap.xml",
        "year_path_re": re.compile(r"/(20(?:1[89]|2[0-9]))/"),   # /2018/../2029/ etc in the path
        "slug_fn": slug_to_pseudo_title_seven,
    },
    "sbs.com.au": {
        "kind": "monthly_index",
        "template": "https://www.sbs.com.au/news/sitemap-article-{yearmonth}.xml",
        "slug_fn": slug_to_pseudo_title_sbs,
    },
}


def _fetch_bytes(url: str, *, timeout: int = 60) -> bytes:
    cached = raw_cache.get("sitemap", url)
    if cached is not None:
        return cached
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    raw_cache.put("sitemap", url, raw)
    return raw


def _fetch_text(url: str, *, timeout: int = 60, gzipped: bool = False) -> str:
    raw = _fetch_bytes(url, timeout=timeout)
    # ABC's CDN sometimes serves .xml.gz URLs already decompressed (content negotiation
    # quirk, not consistent) — only decompress if the bytes are actually gzip-magic.
    if gzipped and raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def _dates(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def extract_url_items(raw: str) -> list[tuple[str, str | None]]:
    """Parse (loc, lastmod) pairs from a sitemap. `cluster_incidents.py` buckets by
    `seendate` and silently drops any article with none at all — a missing lastmod here
    must not become a NULL seendate that vanishes from clustering.
    """
    out = []
    for block in _URL_BLOCK_RE.findall(raw):
        loc_m = _URL_RE.search(f"<url>{block}</url>")
        if not loc_m:
            continue
        lm_m = _LASTMOD_RE.search(block)
        out.append((loc_m.group(1), lm_m.group(1) if lm_m else None))
    if not out:
        # Some sitemaps (e.g. ABC's) have no <url> wrapper at all, just bare <loc> tags.
        out = [(loc, None) for loc in _URL_RE.findall(raw)]
    return out


def _seendate_from_lastmod(lastmod: str | None) -> str | None:
    if not lastmod or len(lastmod) < 10:
        return None
    candidate = lastmod[:10]
    try:
        dt.date.fromisoformat(candidate)
        return candidate
    except ValueError:
        return None


def _insert_candidates(db: sqlite3.Connection, items: list[tuple[str, str | None]], slug_fn,
                        domain: str, query_tag: str, kw, stats: dict, *,
                        date_fn=None, default_date: str | None = None) -> None:
    """`date_fn(loc)` (if given) takes priority over parsed lastmod (used for ABC, whose
    sitemap has no lastmod but embeds the publish date in the URL path). `default_date`
    is the last resort (the calendar day/month a "daily"/"monthly" fetch is already
    scoped to) — always applied rather than ever leaving seendate NULL.
    """
    rows = []
    for loc, lastmod in items:
        pseudo_title = slug_fn(loc)
        if not pseudo_title or not kw.search(pseudo_title):
            continue
        stats["candidates"] += 1
        cu = canonical_url(loc)
        m = match_outlet(cu) if cu else None
        if not m:
            continue
        seendate = (date_fn(loc) if date_fn else None) or _seendate_from_lastmod(lastmod) or default_date
        rows.append((url_hash(cu), cu, SOURCE, m[0],
                     f"[slug, not real headline] {pseudo_title}", seendate, query_tag))
    if rows:
        cur = db.executemany(
            "INSERT OR IGNORE INTO harvest "
            "(url_hash, canonical_url, source, domain, title_at_crawl, seendate, query) "
            "VALUES (?,?,?,?,?,?,?)", rows)
        stats["inserted"] += cur.rowcount


def harvest_daily(db: sqlite3.Connection, start: dt.date, end: dt.date,
                   *, domain: str, dry_run: bool = False) -> dict[str, int]:
    cfg = SITE_CONFIGS[domain]
    kw = keyword_regex()
    dates = list(_dates(start, end))
    LOG.info("plan: %d daily sitemaps for %s (~%.1f h at %.1fs/call)",
             len(dates), domain, len(dates) * REQUEST_DELAY_S / 3600, REQUEST_DELAY_S)
    stats = {"days": 0, "urls_seen": 0, "candidates": 0, "inserted": 0, "errors": 0,
              "skipped_done": 0}
    if dry_run:
        return stats

    tag_prefix = f"sitemap:{domain}"
    done = {r[0] for r in db.execute(
        "SELECT window_start FROM harvest_progress WHERE query_hash = ?", (tag_prefix,))}
    if done:
        LOG.info("resuming: %d days already completed", len(done))

    for d in dates:
        key = d.isoformat()
        if key in done:
            stats["skipped_done"] += 1
            continue
        url = cfg["template"].format(date=d.strftime(cfg.get("date_fmt", "%Y%m%d")))
        try:
            raw = _fetch_text(url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            LOG.warning("fetch failed %s: %s", url, exc)
            stats["errors"] += 1
            time.sleep(REQUEST_DELAY_S)
            continue

        items = extract_url_items(raw)
        stats["urls_seen"] += len(items)
        _insert_candidates(db, items, cfg["slug_fn"], domain, tag_prefix, kw, stats,
                            default_date=key)

        db.execute("INSERT OR REPLACE INTO harvest_progress "
                   "(query_hash, window_start, window_end, n_returned, capped) "
                   "VALUES (?,?,?,?,?)",
                   (tag_prefix, key, key, len(items), 0))
        db.commit()
        stats["days"] += 1
        time.sleep(REQUEST_DELAY_S)

    return stats


def harvest_paginated(db: sqlite3.Connection, start: dt.date, end: dt.date,
                       *, domain: str, dry_run: bool = False) -> dict[str, int]:
    cfg = SITE_CONFIGS[domain]
    kw = keyword_regex()
    tag_prefix = f"sitemap:{domain}"
    LOG.info("plan: up to %d pages for %s, filtering to %s..%s (~%.1f h at %.1fs/call)",
             cfg["max_pages"], domain, start, end, cfg["max_pages"] * REQUEST_DELAY_S / 3600,
             REQUEST_DELAY_S)
    stats = {"pages": 0, "urls_seen": 0, "in_range": 0, "candidates": 0, "inserted": 0,
              "errors": 0, "skipped_done": 0, "not_found": 0}
    if dry_run:
        return stats

    done = {r[0] for r in db.execute(
        "SELECT window_start FROM harvest_progress WHERE query_hash = ?", (tag_prefix,))}
    if done:
        LOG.info("resuming: %d pages already completed", len(done))

    for page in range(cfg["max_pages"]):
        key = str(page)
        if key in done:
            stats["skipped_done"] += 1
            continue
        url = cfg["template"].format(page=page)
        try:
            raw = _fetch_text(url, gzipped=cfg.get("gzipped", False))
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                # Past the last real page — expected once max_pages overshoots. Record it
                # so a resume doesn't re-probe pages already known to be absent.
                stats["not_found"] += 1
                db.execute("INSERT OR REPLACE INTO harvest_progress "
                           "(query_hash, window_start, window_end, n_returned, capped) "
                           "VALUES (?,?,?,?,?)", (tag_prefix, key, key, 0, 0))
                db.commit()
                time.sleep(REQUEST_DELAY_S)
                continue
            LOG.warning("fetch failed %s: %s", url, exc)
            stats["errors"] += 1
            time.sleep(REQUEST_DELAY_S)
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            LOG.warning("fetch failed %s: %s", url, exc)
            stats["errors"] += 1
            time.sleep(REQUEST_DELAY_S)
            continue

        locs = _URL_RE.findall(raw)
        stats["urls_seen"] += len(locs)
        in_range = [loc for loc in locs
                    if (d := cfg["date_fn"](loc)) and start.isoformat() <= d <= end.isoformat()]
        stats["in_range"] += len(in_range)
        items = [(loc, None) for loc in in_range]
        _insert_candidates(db, items, cfg["slug_fn"], domain, tag_prefix, kw, stats,
                            date_fn=cfg["date_fn"])

        db.execute("INSERT OR REPLACE INTO harvest_progress "
                   "(query_hash, window_start, window_end, n_returned, capped) "
                   "VALUES (?,?,?,?,?)",
                   (tag_prefix, key, key, len(locs), 0))
        db.commit()
        stats["pages"] += 1
        time.sleep(REQUEST_DELAY_S)

    return stats


def harvest_index_list(db: sqlite3.Connection, start: dt.date, end: dt.date,
                        *, domain: str, dry_run: bool = False) -> dict[str, int]:
    """Fetch a top-level index once, then only its sub-files whose path falls in range."""
    cfg = SITE_CONFIGS[domain]
    kw = keyword_regex()
    tag_prefix = f"sitemap:{domain}"
    stats = {"files": 0, "urls_seen": 0, "candidates": 0, "inserted": 0, "errors": 0,
              "skipped_done": 0}
    if dry_run:
        return stats

    try:
        index_raw = _fetch_text(cfg["index_url"])
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        LOG.warning("fetch failed %s: %s", cfg["index_url"], exc)
        stats["errors"] += 1
        return stats
    time.sleep(REQUEST_DELAY_S)

    all_files = _URL_RE.findall(index_raw)
    years = {str(y) for y in range(start.year, end.year + 1)}
    files = [f for f in all_files
             if (m := cfg["year_path_re"].search(f)) and m.group(1) in years]
    LOG.info("plan: %d sub-files for %s (of %d total, filtered to %s..%s) (~%.1f h at %.1fs/call)",
             len(files), domain, len(all_files), start, end, len(files) * REQUEST_DELAY_S / 3600,
             REQUEST_DELAY_S)

    done = {r[0] for r in db.execute(
        "SELECT window_start FROM harvest_progress WHERE query_hash = ?", (tag_prefix,))}
    if done:
        LOG.info("resuming: %d files already completed", len(done))

    for f in files:
        key = f
        if key in done:
            stats["skipped_done"] += 1
            continue
        try:
            raw = _fetch_text(f)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            LOG.warning("fetch failed %s: %s", f, exc)
            stats["errors"] += 1
            time.sleep(REQUEST_DELAY_S)
            continue

        items = extract_url_items(raw)
        stats["urls_seen"] += len(items)
        # No reliable file-level fallback date here — a weekly index file spans ~7 days,
        # so an item with no lastmod is dropped (silent gap, not a wrong seendate).
        _insert_candidates(db, items, cfg["slug_fn"], domain, tag_prefix, kw, stats)

        db.execute("INSERT OR REPLACE INTO harvest_progress "
                   "(query_hash, window_start, window_end, n_returned, capped) "
                   "VALUES (?,?,?,?,?)", (tag_prefix, key, key, len(items), 0))
        db.commit()
        stats["files"] += 1
        time.sleep(REQUEST_DELAY_S)

    return stats


def _months(start: dt.date, end: dt.date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def harvest_monthly(db: sqlite3.Connection, start: dt.date, end: dt.date,
                     *, domain: str, dry_run: bool = False) -> dict[str, int]:
    cfg = SITE_CONFIGS[domain]
    kw = keyword_regex()
    tag_prefix = f"sitemap:{domain}"
    months = list(_months(start, end))
    LOG.info("plan: %d monthly sitemaps for %s (~%.1f h at %.1fs/call)",
             len(months), domain, len(months) * REQUEST_DELAY_S / 3600, REQUEST_DELAY_S)
    stats = {"months": 0, "urls_seen": 0, "candidates": 0, "inserted": 0, "errors": 0,
              "skipped_done": 0}
    if dry_run:
        return stats

    done = {r[0] for r in db.execute(
        "SELECT window_start FROM harvest_progress WHERE query_hash = ?", (tag_prefix,))}
    if done:
        LOG.info("resuming: %d months already completed", len(done))

    for y, m in months:
        key = f"{y:04d}-{m:02d}"
        if key in done:
            stats["skipped_done"] += 1
            continue
        url = cfg["template"].format(yearmonth=key)
        try:
            raw = _fetch_text(url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            LOG.warning("fetch failed %s: %s", url, exc)
            stats["errors"] += 1
            time.sleep(REQUEST_DELAY_S)
            continue

        items = extract_url_items(raw)
        stats["urls_seen"] += len(items)
        # Fallback to the 1st of the month if an item has no lastmod — coarse, but keeps
        # it inside clustering rather than silently vanishing (see cluster_incidents.py's
        # date-bucketing skip for seendate IS NULL).
        _insert_candidates(db, items, cfg["slug_fn"], domain, tag_prefix, kw, stats,
                            default_date=f"{key}-01")

        db.execute("INSERT OR REPLACE INTO harvest_progress "
                   "(query_hash, window_start, window_end, n_returned, capped) "
                   "VALUES (?,?,?,?,?)", (tag_prefix, key, key, len(items), 0))
        db.commit()
        stats["months"] += 1
        time.sleep(REQUEST_DELAY_S)

    return stats


def harvest(db: sqlite3.Connection, start: dt.date, end: dt.date,
            *, domain: str, dry_run: bool = False) -> dict[str, int]:
    kind = SITE_CONFIGS[domain]["kind"]
    if kind == "daily":
        return harvest_daily(db, start, end, domain=domain, dry_run=dry_run)
    if kind == "paginated":
        return harvest_paginated(db, start, end, domain=domain, dry_run=dry_run)
    if kind == "index_list":
        return harvest_index_list(db, start, end, domain=domain, dry_run=dry_run)
    if kind == "monthly_index":
        return harvest_monthly(db, start, end, domain=domain, dry_run=dry_run)
    raise ValueError(f"unknown sitemap kind for {domain!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--domain", default="smh.com.au", choices=list(SITE_CONFIGS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                         format="%(asctime)s %(levelname)-7s %(message)s")

    db = open_db(args.db)
    stats = harvest(db, dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end),
                     domain=args.domain, dry_run=args.dry_run)
    LOG.info("done: %s", stats)


if __name__ == "__main__":
    main()
