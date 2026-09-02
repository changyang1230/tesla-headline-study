"""Fetch real article HTML for candidate-cluster URLs and extract headline + body text.

Sitemap-derived candidates only ever gave us a URL and a slug-derived pseudo-title (see
sitemap_harvest.py) — never the real rendered headline or body. This module fetches the
actual page so `headline_names_make` can be computed mechanically (lexicon.py) against
the real headline, and so `llm_coding`-style extraction has real body text to read.

Same per-outlet access rules established for harvesting apply here: direct fetch for
outlets whose robots.txt permits general `*` access (SMH, Nine, ABC, 7NEWS, SBS, Daily
Mail — all already used for harvesting); news.com.au is fetched via the Wayback Machine
snapshot closest to the article's seendate, never live, for the same robots.txt reason
documented in wayback_harvest.py.

Extraction uses `trafilatura` (a real article-extraction library — a hand-rolled
stdlib tag-stripper was tried first and left too much nav/sidebar/"related articles"
noise mixed into the body to read reliably; see git history if curious). Falls back to
a minimal stdlib title+paragraph pass only if trafilatura is unavailable or returns
nothing.

Usage:
    python -m src.fetch_bodies --db data/study.db --incident-csv output/candidate_incidents.csv
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import logging
import pathlib
import re
import sqlite3
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

from . import raw_cache

try:
    import trafilatura
except ImportError:
    trafilatura = None

LOG = logging.getLogger("fetch_bodies")

USER_AGENT = (
    "tesla-headline-salience-study/0.2 "
    "(non-commercial media-content research; contact via repository)"
)
REQUEST_DELAY_S = 2.0
BODIES_DIR = pathlib.Path("data/bodies")

#: Fetched directly. news.com.au is deliberately absent — see module docstring.
DIRECT_DOMAINS = {"smh.com.au", "nine.com.au", "abc.net.au", "7news.com.au",
                   "sbs.com.au", "dailymail.com"}


class _TextExtractor(HTMLParser):
    """Minimal HTML -> (title, body text). Drops script/style/nav/header/footer/aside."""

    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript"}

    def __init__(self):
        super().__init__()
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self._in_title = False
        self._skip_depth = 0
        self._h1_seen = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        else:
            self.body_parts.append(text)

    @property
    def title(self) -> str:
        return html.unescape(" ".join(self.title_parts)).strip()

    @property
    def body(self) -> str:
        return html.unescape("\n".join(self.body_parts)).strip()


def extract(raw_html: str) -> tuple[str, str]:
    if trafilatura is not None:
        result = trafilatura.extract(
            raw_html, output_format="json", with_metadata=True,
            favor_precision=True,   # prefer missing a paragraph over pulling in nav/related-links noise
        )
        if result:
            import json as _json
            data = _json.loads(result)
            title, body = (data.get("title") or "").strip(), (data.get("text") or "").strip()
            if title and len(body) >= 200:
                return title, body
    # Fallback: minimal stdlib tag-stripper, used only if trafilatura is unavailable or
    # returned too little (e.g. a heavily JS-rendered page trafilatura can't parse).
    p = _TextExtractor()
    p.feed(raw_html)
    return p.title, p.body


def article_id(canonical_url: str) -> str:
    return hashlib.sha1(canonical_url.encode("utf-8")).hexdigest()[:16]


def _fetch_direct(url: str, *, timeout: int = 30) -> str | None:
    cached = raw_cache.get("article_html", url)
    if cached is not None:
        return cached.decode("utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        raw_cache.put("article_html", url, raw)
        return raw.decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        LOG.warning("fetch failed %s: %s", url, exc)
        return None


def _fetch_wayback(url: str, target_date: dt.date, *, timeout: int = 60) -> str | None:
    from .wayback_harvest import BACKOFFS, WAYBACK_TEMPLATE
    ts = target_date.strftime("%Y%m%d") + "000000"
    wb_url = WAYBACK_TEMPLATE.format(ts=ts, original=url)
    cached = raw_cache.get("article_html", wb_url)
    if cached is not None:
        return cached.decode("utf-8", errors="replace")
    req = urllib.request.Request(wb_url, headers={"User-Agent": USER_AGENT})
    for attempt, backoff in enumerate(BACKOFFS):
        if backoff:
            time.sleep(backoff)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            raw_cache.put("article_html", wb_url, raw)
            return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                continue
            if exc.code in (403, 404):
                return None
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
    return None


def fetch_one(db: sqlite3.Connection, url_hash: str, canonical_url: str, domain: str,
              outlet: str, seendate: str | None) -> str | None:
    """Fetch, extract, save to data/bodies/, insert/patch the article row. Returns the
    article_id on success, None on failure (never raises — repository rule)."""
    aid = article_id(canonical_url)
    body_path = BODIES_DIR / f"{aid}.txt"
    if body_path.exists():
        return aid

    if domain in DIRECT_DOMAINS:
        raw = _fetch_direct(canonical_url)
    elif domain == "news.com.au":
        target = dt.date.fromisoformat(seendate) if seendate else dt.date(2024, 1, 1)
        raw = _fetch_wayback(canonical_url, target)
    else:
        LOG.warning("no fetch strategy for domain %s, skipping %s", domain, canonical_url)
        return None

    if not raw:
        return None
    title, body = extract(raw)
    if not title or len(body) < 200:
        LOG.warning("thin extraction (title=%r, body_len=%d) for %s", title[:60], len(body), canonical_url)
        return None

    BODIES_DIR.mkdir(parents=True, exist_ok=True)
    body_path.write_text(body, encoding="utf-8")

    from .gdelt_harvest import OUTLET_DOMAINS
    meta = OUTLET_DOMAINS.get(domain)
    outlet_name, outlet_group, outlet_register = meta if meta else (outlet, outlet, "tabloid")

    from .lexicon import identified_makes
    makes = identified_makes(title)
    headline_names_make = int(bool(makes))

    db.execute(
        "INSERT OR IGNORE INTO article "
        "(article_id, url, outlet, outlet_group, outlet_register, headline, "
        " headline_source, publish_datetime, headline_names_make, coded_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
        (aid, canonical_url, outlet_name, outlet_group, outlet_register, title,
         "wayback" if domain == "news.com.au" else "live", seendate, headline_names_make))
    db.commit()
    return aid


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--urls", nargs="+", help="specific canonical URLs to fetch (space-separated)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    db = sqlite3.connect(args.db, timeout=60.0)
    db.execute("PRAGMA busy_timeout = 60000")
    db.row_factory = sqlite3.Row
    if not args.urls:
        raise SystemExit("pass --urls (this module is driven by promote_incidents.py normally)")

    ok, failed = 0, 0
    for url in args.urls:
        row = db.execute(
            "SELECT url_hash, canonical_url, domain, seendate FROM harvest WHERE canonical_url=?",
            (url,)).fetchone()
        if not row:
            LOG.warning("not in harvest table: %s", url)
            failed += 1
            continue
        aid = fetch_one(db, row["url_hash"], row["canonical_url"], row["domain"], row["domain"], row["seendate"])
        if aid:
            ok += 1
        else:
            failed += 1
        time.sleep(REQUEST_DELAY_S)
    LOG.info("done: %d ok, %d failed", ok, failed)


if __name__ == "__main__":
    main()
