"""LLM-assisted incident coding (Codebook section 1, lean-track section 8.2).

Claude extracts incident-level variables from article body text into the fixed schema.
You adjudicate a sample and every disagreement. This replaces a second human coder — it
does not replace the coder.

Three safeguards, in order of importance:

1. **Headline blinding.** When determining the index vehicle, the model sees body text
   with headlines and standfirsts stripped. Codebook 1.2 requires the index vehicle to be
   determined without reading the headline; if the headline drove exposure assignment, the
   study would measure its own outcome. `strip_headlines()` enforces this and
   `test_llm_coding.py` asserts it.

2. **It never codes the outcome.** `headline_names_make` comes from the frozen lexicon,
   mechanically. Nothing in this file touches it. A model that knows the hypothesis must
   not be deciding whether a headline names a make.

3. **Evidence and confidence per field.** Every extracted value carries a verbatim
   supporting quote and a confidence. Low confidence and missing evidence are routed to
   human review rather than silently accepted.

Usage:
    python -m src.llm_coding --db data/study.db --limit 20
    python -m src.llm_coding --db data/study.db --incident 20231106-VIC-01 --show
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import re
import sqlite3
import textwrap

LOG = logging.getLogger("llm_coding")

MODEL = "claude-opus-5"

#: Fields below this confidence are queued for human review rather than accepted.
CONFIDENCE_FLOOR = 0.75

#: Fields the model may never set. The primary outcome is mechanical (safeguard 2), and
#: eligibility is a study decision, not an extraction.
FORBIDDEN_FIELDS = frozenset({
    "headline_names_make", "headline_names_make_strict", "headline_names_second_make",
    "body_names_make", "first_mention_position", "eligible", "is_seed_example",
})

SYSTEM = """You are a data extraction assistant for a media-content study of Australian \
road-vehicle incidents. You extract facts from news article text into a fixed schema.

Rules:
- Extract only what the text supports. Never infer, guess, or fill from background \
knowledge about Australian road incidents.
- If the text does not establish a field, return null for it with confidence 0.
- Every non-null field needs a verbatim quote from the supplied text as evidence.
- You are given body text only. Headlines have been removed deliberately. Do not \
speculate about what a headline might have said.
- Vehicle makes: give the badge on the car (an MG4 is "MG"). Give the make in \
`index_make` and the model separately in `index_model`.
- The index vehicle is the one whose movement or condition constitutes the event: the \
single vehicle in a single-vehicle crash; the striking vehicle when a pedestrian or \
cyclist is hit; the burning vehicle in a fire; otherwise the vehicle police describe as \
initiating, and failing that the one whose occupants were most seriously hurt. If the \
text does not resolve which vehicle that is, set index_make to null and say so in notes.
- Report counts of deaths and serious injuries across all parties, not just one vehicle.
- Be conservative. A null the human reviewer fills in costs far less than a confident \
wrong value they do not notice."""

SCHEMA = {
    "type": "object",
    "properties": {
        "incident_date": {"type": ["string", "null"],
                          "description": "ISO date the incident occurred, not when reported"},
        "state": {"type": ["string", "null"],
                  "enum": ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "NT", "ACT", None]},
        "locality": {"type": ["string", "null"], "description": "Suburb or town"},
        "deaths": {"type": ["integer", "null"]},
        "serious_injuries": {"type": ["integer", "null"]},
        "victim_child": {"type": ["boolean", "null"],
                         "description": "Any person killed or seriously injured was under 18"},
        "incident_type": {"type": ["string", "null"],
                          "enum": ["pedestrian_cyclist_struck", "single_vehicle_fire",
                                   "occupant_fatal_collision", "occupant_serious_collision",
                                   "other", None]},
        "multi_vehicle": {"type": ["boolean", "null"]},
        "fire_involved": {"type": ["boolean", "null"]},
        "index_make": {"type": ["string", "null"]},
        "index_model": {"type": ["string", "null"]},
        "index_vehicle_year": {"type": ["integer", "null"]},
        "second_make": {"type": ["string", "null"],
                        "description": "Other vehicle's make, only if exactly two vehicles"},
        "all_makes": {"type": ["string", "null"], "description": "Pipe-separated, 3+ vehicles"},
        "adas_alleged": {"type": ["boolean", "null"],
                         "description": "Autopilot, FSD, self-driving or lane-keeping raised"},
        "driver_notable": {"type": ["boolean", "null"],
                           "description": "Driver is a public figure independently of this incident"},
        "make_source_quote": {"type": ["string", "null"],
                              "description": "Verbatim sentence establishing the vehicle make"},
        "evidence": {
            "type": "object",
            "description": "Verbatim supporting quote for each non-null field, keyed by field name",
            "additionalProperties": {"type": "string"},
        },
        "confidence": {
            "type": "object",
            "description": "0.0-1.0 confidence for each field, keyed by field name",
            "additionalProperties": {"type": "number"},
        },
        "index_vehicle_ambiguous": {
            "type": "boolean",
            "description": "True if the text does not resolve which vehicle is the index vehicle",
        },
        "notes": {"type": "string"},
    },
    "required": ["incident_date", "state", "locality", "deaths", "serious_injuries",
                 "victim_child", "incident_type", "multi_vehicle", "fire_involved",
                 "index_make", "index_model", "index_vehicle_year", "second_make",
                 "all_makes", "adas_alleged", "driver_notable", "make_source_quote",
                 "evidence", "confidence", "index_vehicle_ambiguous", "notes"],
    "additionalProperties": False,
}


def strip_headlines(body: str, headline: str = "", standfirst: str = "") -> str:
    """Remove the headline and standfirst from body text (safeguard 1).

    Also drops the common scraped-article artefacts that reproduce the headline: an
    all-caps or title-case first line, and any line that is a near-copy of the known
    headline. Over-stripping is the safe direction here.
    """
    text = body or ""
    for lead in (headline, standfirst):
        if lead and lead.strip():
            text = re.sub(re.escape(lead.strip()), " ", text, flags=re.IGNORECASE)
            # Scraped pages repeat the headline with drifting punctuation and spacing.
            # \W* between words absorbs commas, colons and runs of space, and cannot skip
            # a word (\W excludes word characters), so this can't over-match.
            loose = r"\W*".join(re.escape(w) for w in lead.split() if w)
            if loose:
                text = re.sub(loose, " ", text, flags=re.IGNORECASE)
    lines = [ln for ln in text.split("\n")]
    if lines and lines[0].strip() and len(lines[0].split()) <= 20 and lines[0].strip().isupper():
        lines = lines[1:]
    return "\n".join(lines).strip()


def build_prompt(incident_id: str, articles: list[dict]) -> str:
    """Article bodies for one incident, headline-stripped and clearly delimited."""
    parts = [f"Incident reference: {incident_id}",
             f"You have {len(articles)} article(s) about the same incident.",
             "Headlines have been removed deliberately — do not ask for them.", ""]
    for i, a in enumerate(articles, 1):
        clean = strip_headlines(a.get("body", ""), a.get("headline", ""), a.get("standfirst", ""))
        parts.append(f"<article n=\"{i}\" outlet=\"{a.get('outlet', 'unknown')}\" "
                     f"published=\"{a.get('publish_datetime', 'unknown')}\">")
        parts.append(textwrap.shorten(clean, width=12000, placeholder=" [...truncated]")
                     if len(clean) > 12000 else clean)
        parts.append("</article>\n")
    parts.append("Extract the incident-level variables into the required schema.")
    return "\n".join(parts)


def code_incident(client, incident_id: str, articles: list[dict], *, model: str = MODEL) -> dict:
    """One structured extraction call for one incident."""
    response = client.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": build_prompt(incident_id, articles)}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"refused: {getattr(response.stop_details, 'category', None)}")
    text = next(b.text for b in response.content if b.type == "text")
    out = json.loads(text)
    for f in FORBIDDEN_FIELDS:
        out.pop(f, None)  # safeguard 2: belt and braces
    return out


def needs_review(coded: dict) -> list[str]:
    """Fields to route to a human (Codebook 4, lean track).

    A model that hedges is doing its job; the hedges are what the human should spend
    their attention on.
    """
    flags = []
    if coded.get("index_vehicle_ambiguous"):
        flags.append("index_vehicle_ambiguous")
    if coded.get("index_make") and not coded.get("make_source_quote"):
        flags.append("index_make:no_evidence_quote")
    conf = coded.get("confidence") or {}
    evid = coded.get("evidence") or {}
    meta = ("evidence", "confidence", "notes", "index_vehicle_ambiguous", "make_source_quote")
    for field, value in coded.items():
        if field in meta:
            continue
        if value is None:
            continue
        if conf.get(field, 0.0) < CONFIDENCE_FLOOR:
            flags.append(f"{field}:low_confidence")
        elif field not in evid:
            flags.append(f"{field}:no_evidence")
    return flags


# ------------------------------------------------------------------- persistence

WRITABLE = ("incident_date", "state", "locality", "deaths", "serious_injuries",
            "victim_child", "incident_type", "multi_vehicle", "fire_involved",
            "index_make", "index_model", "index_vehicle_year", "second_make",
            "all_makes", "adas_alleged", "driver_notable")


def store(db: sqlite3.Connection, incident_id: str, coded: dict, flags: list[str]) -> None:
    """Write the machine coding into dual_coding as coder 'claude', never into `incident`.

    The `incident` table holds adjudicated values only. Machine output is one coder's
    opinion and is stored as such, so agreement can be recomputed later and so a human
    decision is never silently overwritten by a re-run.
    """
    from .lexicon import canonical_make
    rows = []
    for f in WRITABLE:
        v = coded.get(f)
        if f in ("index_make", "second_make") and v:
            v = canonical_make(v) or v
        rows.append(("incident", incident_id, f, "claude", None if v is None else str(v)))
    rows.append(("incident", incident_id, "_review_flags", "claude", "|".join(flags)))
    rows.append(("incident", incident_id, "_notes", "claude", coded.get("notes", "")))
    rows.append(("incident", incident_id, "_make_quote", "claude",
                 coded.get("make_source_quote") or ""))
    db.executemany("INSERT OR REPLACE INTO dual_coding "
                   "(unit_type, unit_id, variable, coder, value) VALUES (?,?,?,?,?)", rows)
    db.commit()


def load_articles(db: sqlite3.Connection, incident_id: str) -> list[dict]:
    db.row_factory = sqlite3.Row
    body_dir = pathlib.Path("data/bodies")
    out = []
    for r in db.execute("SELECT article_id, outlet, headline, standfirst, publish_datetime "
                        "FROM article WHERE incident_id=? ORDER BY publish_datetime",
                        (incident_id,)):
        f = body_dir / f"{r['article_id']}.txt"
        if not f.exists():
            continue
        out.append({"outlet": r["outlet"], "headline": r["headline"],
                    "standfirst": r["standfirst"], "publish_datetime": r["publish_datetime"],
                    "body": f.read_text(encoding="utf-8", errors="replace")})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--incident", default=None, help="code a single incident")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--show", action="store_true", help="print the coding instead of storing it")
    ap.add_argument("--recode", action="store_true", help="re-code incidents already coded")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        import anthropic
    except ImportError:
        raise SystemExit("pip install anthropic")
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        LOG.info("no API key env var — relying on an `ant auth login` profile")
    client = anthropic.Anthropic()

    db = sqlite3.connect(args.db)
    if args.incident:
        targets = [args.incident]
    else:
        done = {r[0] for r in db.execute(
            "SELECT DISTINCT unit_id FROM dual_coding WHERE coder='claude' AND unit_type='incident'")}
        targets = [r[0] for r in db.execute("SELECT incident_id FROM incident ORDER BY incident_id")]
        if not args.recode:
            targets = [t for t in targets if t not in done]
        if args.limit:
            targets = targets[:args.limit]

    LOG.info("coding %d incident(s) with %s", len(targets), args.model)
    flagged = 0
    for inc in targets:
        articles = load_articles(db, inc)
        if not articles:
            LOG.warning("%s: no body text on disk, skipping", inc)
            continue
        try:
            coded = code_incident(client, inc, articles, model=args.model)
        except Exception as exc:   # repository rule: log and continue
            LOG.warning("%s: coding failed (%s)", inc, exc)
            continue
        flags = needs_review(coded)
        flagged += bool(flags)
        if args.show:
            print(json.dumps({"incident": inc, "coded": coded, "review_flags": flags}, indent=2))
        else:
            store(db, inc, coded, flags)
            LOG.info("%s: make=%s deaths=%s flags=%s", inc, coded.get("index_make"),
                     coded.get("deaths"), ",".join(flags) or "none")
    LOG.info("done; %d incident(s) carry review flags and need your attention", flagged)
    LOG.info("machine coding is stored as coder='claude' in dual_coding — the `incident` "
             "table still needs your adjudicated values")


if __name__ == "__main__":
    main()
