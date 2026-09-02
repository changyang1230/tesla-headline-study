"""Post-discovery topical classification: does this candidate's title actually describe
a road-vehicle crash (car/truck/motorcycle/bus/ute), or is it noise the event-vocabulary
match picked up incidentally (aviation, sports "collision", stock-market "crash",
metaphor, etc.)?

This is deliberately NOT a discovery-time or outcome decision — it runs entirely off the
title/slug text, never touches make/brand, and never influences which brand gets found.
Protocol §6.1's brand-agnostic rule is about discovery (a query must not contain "Tesla"
so Tesla stories aren't easier to find); this is a relevance screen on already-harvested
candidates, analogous to the Codebook's human "substantive" article-inclusion judgment,
just automated because the loosened discovery vocabulary (dropped outcome-term
requirement, see queries.py) produces far more non-vehicle noise than a human could
screen by hand at this volume.

Batches titles (cheap, short text) rather than one call per title — a single incident
read (llm_coding.py) is a different, much more expensive task this deliberately avoids
triggering at this stage.

Usage:
    python -m src.classify_vehicle --db data/study.db
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import subprocess

LOG = logging.getLogger("classify_vehicle")

MODEL = "haiku"
BATCH_SIZE = 80

SYSTEM = """You classify Australian news headlines by topic. You are given a numbered \
list of headlines (some are URL-slug-derived, hyphens replaced with spaces, ignore \
formatting oddities). For EACH numbered item, decide: does it describe a real-world \
ROAD VEHICLE crash or collision (car, truck, motorcycle, bus, ute, van, single-vehicle \
rollover, pedestrian/cyclist struck by a vehicle)?

Answer NO for: aviation crashes (plane, helicopter), boat/maritime incidents, train \
crashes, sports "collisions" (players colliding, a team "crashing out" of a \
tournament), stock market or financial "crashes", metaphorical usage ("her marriage \
crashed", "the app crashed"), and anything not about a road vehicle incident.

When genuinely uncertain, answer YES — a human will still verify every candidate before \
it becomes real data; the cost of a false positive here is a wasted review, the cost of \
a false negative is losing a real incident permanently.

Respond with ONLY a JSON array of the item numbers (integers) that are YES — road \
vehicle crashes. Example: [1,3,4,7]. No other text."""


def _claude_bin() -> str:
    return os.environ.get("CLAUDE_BIN", "claude")


def _claude_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}


def classify_batch(items: list[tuple[str, str]], *, model: str = MODEL,
                    timeout: int = 120) -> set[str]:
    """items: [(url_hash, title), ...]. Returns the set of url_hash values judged to be
    road-vehicle crashes."""
    numbered = "\n".join(f"{i+1}. {title}" for i, (_, title) in enumerate(items))
    result = subprocess.run(
        [_claude_bin(), "-p", "--model", model, "--system-prompt", SYSTEM,
         "--no-session-persistence"],
        input=numbered, capture_output=True, text=True, timeout=timeout, env=_claude_env(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p exit {result.returncode}: "
                            f"{(result.stdout or result.stderr).strip()[:300]}")
    text = result.stdout.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    indices = json.loads(text)
    yes_hashes = set()
    for i in indices:
        idx = int(i) - 1
        if 0 <= idx < len(items):
            yes_hashes.add(items[idx][0])
    return yes_hashes


def _batches(rows: list[tuple[str, str]], size: int):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def classify_one_batch(db_path: str, batch: list[tuple[str, str]], model: str) -> tuple[int, int]:
    """Own DB connection per worker thread. Returns (n_yes, n_no)."""
    db = sqlite3.connect(db_path, timeout=60.0)
    db.execute("PRAGMA busy_timeout = 60000")
    try:
        try:
            yes_hashes = classify_batch(batch, model=model)
        except Exception as exc:  # repository rule: log and continue
            LOG.warning("batch of %d failed (%s), leaving unclassified for retry", len(batch), exc)
            return (0, 0)
        rows = [(1 if uh in yes_hashes else 0, uh) for uh, _ in batch]
        db.executemany("UPDATE harvest SET is_vehicle_crash=? WHERE url_hash=?", rows)
        db.commit()
        n_yes = sum(1 for v, _ in rows if v == 1)
        return (n_yes, len(rows) - n_yes)
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--start", default=None, help="only classify seendate >= this (ISO date)")
    ap.add_argument("--end", default=None, help="only classify seendate <= this (ISO date)")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    db = sqlite3.connect(args.db, timeout=60.0)
    db.execute("PRAGMA busy_timeout = 60000")

    sql = "SELECT url_hash, title_at_crawl FROM harvest WHERE is_vehicle_crash IS NULL"
    params: list[str] = []
    if args.start:
        sql += " AND seendate >= ?"
        params.append(args.start)
    if args.end:
        sql += " AND seendate <= ?"
        params.append(args.end)
    rows = db.execute(sql, params).fetchall()
    if args.limit:
        rows = rows[:args.limit]

    if not rows:
        LOG.info("nothing to classify")
        return

    batches = list(_batches(rows, args.batch_size))
    LOG.info("classifying %d candidates in %d batches of ~%d, %d worker(s), model %s",
             len(rows), len(batches), args.batch_size, args.workers, args.model)

    import concurrent.futures
    total_yes, total_no = 0, 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(classify_one_batch, args.db, b, args.model) for b in batches]
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            n_yes, n_no = fut.result()
            total_yes += n_yes
            total_no += n_no
            LOG.info("batch %d/%d done (running total: %d yes, %d no)",
                     i, len(batches), total_yes, total_no)

    LOG.info("done: %d road-vehicle, %d excluded, %d total classified",
             total_yes, total_no, total_yes + total_no)


if __name__ == "__main__":
    main()
