"""Export a public-facing data appendix: every eligible incident, every article, every
headline and URL — the transparency backing for `output/primary_result.md` (and any
write-up built on it, e.g. `output/medium_writeup_draft.md`).

Tesla incidents get full detail up front (there are only 3; every reader will want to
check them). Everything else is listed completely but compactly, grouped by make.

Usage:
    python -m src.export_appendix --db data/study.db --out output/appendix.md
"""

from __future__ import annotations

import argparse
import collections
import sqlite3

from .primary import MIN_OUTLETS


def load_eligible(db: sqlite3.Connection, *, min_outlets: int = MIN_OUTLETS) -> list[dict]:
    """Only incidents that actually clear the coverage bar used in the primary result.

    `incident.eligible=1` means "a human confirmed this is a real, correctly-coded
    incident" — it does NOT mean "meets the outlet threshold." `primary.py` applies that
    threshold separately, at analysis time, so the same adjudicated pool can be re-run at
    different `--min-outlets` values without re-adjudicating. That split is deliberate,
    but it means the raw `eligible=1` set includes incidents that never enter any
    reported probability, CI, or p-value — listing them here without applying the same
    filter is misleading, not transparent.
    """
    db.row_factory = sqlite3.Row
    all_eligible = db.execute(
        "SELECT incident_id, incident_date, index_make FROM incident "
        "WHERE eligible=1 ORDER BY incident_date").fetchall()
    incidents = []
    for inc in all_eligible:
        articles = [dict(r) for r in db.execute(
            "SELECT outlet, headline, url, headline_names_make FROM article "
            "WHERE incident_id=? AND excluded=0 AND substantive=1 ORDER BY publish_datetime",
            (inc["incident_id"],))]
        if len({a["outlet"] for a in articles}) < min_outlets:
            continue
        incidents.append({
            "incident_id": inc["incident_id"],
            "incident_date": inc["incident_date"],
            "make": inc["index_make"] or "(not established)",
            "articles": articles,
        })
    return incidents


def render_incident_full(inc: dict) -> list[str]:
    L = [f"### {inc['incident_date']} — {inc['make']}  `{inc['incident_id']}`", ""]
    for a in inc["articles"]:
        tag = " **[names make]**" if a["headline_names_make"] else ""
        L.append(f"- **{a['outlet']}** — [{a['headline']}]({a['url']}){tag}")
    L.append("")
    return L


def render_incident_compact(inc: dict) -> list[str]:
    n_named = sum(1 for a in inc["articles"] if a["headline_names_make"])
    L = [f'<details markdown="1"><summary><strong>{inc["incident_date"]}</strong> — '
         f"{inc['incident_id']} — {len(inc['articles'])} article(s), "
         f"{n_named} headline(s) name the make</summary>", ""]
    for a in inc["articles"]:
        tag = " **[names make]**" if a["headline_names_make"] else ""
        L.append(f"- **{a['outlet']}** — [{a['headline']}]({a['url']}){tag}")
    L.append("")
    L.append("</details>")
    L.append("")
    return L


def build(incidents: list[dict], *, min_outlets: int) -> str:
    L: list[str] = []
    w = L.append

    tesla = [i for i in incidents if i["make"] == "Tesla"]
    others = [i for i in incidents if i["make"] != "Tesla"]

    w("# Data appendix — every incident used in the primary result, every headline, every link")
    w("")
    w(f"Backing data for the main write-up's primary result. **{len(incidents)}** incidents — "
      f"human-adjudicated as real and correctly coded, AND covered by ≥{min_outlets} of "
      f"the top 10 Australian outlets, the same threshold applied before an "
      f"incident enters any reported probability, CI, or p-value. Every incident here "
      f"passed human review — see the main write-up for the full methodology and caveats.")
    w("")
    w("**[names make]** marks a headline that names the vehicle's make — the outcome "
      "variable the whole study measures.")
    w("")

    w("## Tesla incidents (all 3)")
    w("")
    for inc in tesla:
        L.extend(render_incident_full(inc))

    w("## Every other incident, by make")
    w("")
    w("Collapsed by default — click to expand any incident's articles.")
    w("")
    by_make: dict[str, list[dict]] = collections.defaultdict(list)
    for inc in others:
        by_make[inc["make"]].append(inc)

    for make, incs in sorted(by_make.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        w(f"### {make} ({len(incs)} incident{'s' if len(incs) != 1 else ''})")
        w("")
        for inc in incs:
            L.extend(render_incident_compact(inc))

    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--out", default="output/appendix.md")
    ap.add_argument("--min-outlets", type=int, default=MIN_OUTLETS,
                     help="only include incidents covered by at least this many outlets "
                          "(default matches primary.py's own threshold)")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    incidents = load_eligible(db, min_outlets=args.min_outlets)
    db.close()

    text = build(incidents, min_outlets=args.min_outlets)
    import pathlib
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {len(incidents)} incident(s) to {out}")


if __name__ == "__main__":
    main()
