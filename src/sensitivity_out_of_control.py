"""Sensitivity check: is the Tesla headline-naming effect actually a "dramatic
out-of-control crash" effect — e.g. cars crashing into buildings, going airborne,
rolling — rather than something specific to the Tesla brand?

Motivated by a direct counter-example the user found: a car ploughed into a Canberra
shopping centre BWS store, killing a 4-year-old boy (incident `20260118-01`) — a
textbook "out of control" narrative, same shape as the Westfield-restaurant and
Adelaide-bollard Tesla incidents — yet the make was never named, not even in the body
text. That alone shows "out of control" framing doesn't guarantee brand naming. This
script checks it properly, dataset-wide: restrict the Tesla vs. non-Tesla comparison to
ONLY incidents matching an out-of-control/into-structure narrative, and see whether the
gap survives within that matched subgroup.

Exploratory, post-hoc, unadjusted for multiplicity — like the luxury-brand and outlet
robustness checks in `output/medium_writeup_draft.md` §3.3-3.4, this was not part of the
pre-registered protocol. Classification is a headline+body-text keyword regex, not a
Codebook-defined field (`incident_type` is unpopulated for most of the dataset).

Usage:
    python -m src.sensitivity_out_of_control --db data/study.db
"""

from __future__ import annotations

import argparse
import re
import sqlite3

from .primary import load_rows, to_incidents, permutation_p

OOC_PATTERNS = [
    r'\bploughs? into\b', r'\bplowed into\b', r'\bcrash(?:es|ed)? into\b',
    r'\bsmash(?:es|ed)? into\b', r'\bcrashed through\b', r'\bploughed through\b',
    r'\bairborne\b', r'\bout of control\b', r'\brunaway\b', r'\blos(?:es|t) control\b',
    r'\bloss of control\b', r'\brolled\b', r'\brollover\b', r'\bflipped\b',
    r'\bmounts? (?:the )?(?:footpath|kerb|curb)\b', r'\bmounted (?:the )?(?:footpath|kerb|curb)\b',
    r'\binto (?:a |the )?(?:shop|store|building|house|home|restaurant|cafe|bar|pub|wall|'
    r'fence|pole|bollard|shopfront|shopping centre|shopping center)\b',
]
OOC_RE = re.compile('|'.join(OOC_PATTERNS), re.IGNORECASE)


def is_out_of_control(db: sqlite3.Connection, incident_id: str) -> bool:
    arts = db.execute("SELECT article_id, headline FROM article WHERE incident_id=?",
                       (incident_id,)).fetchall()
    if any(OOC_RE.search(headline or '') for _, headline in arts):
        return True
    for article_id, _ in arts:
        try:
            text = open(f'data/bodies/{article_id}.txt', encoding='utf-8').read()
        except FileNotFoundError:
            continue
        if OOC_RE.search(text):
            return True
    return False


def summarize(label: str, incs: list[dict]) -> None:
    k = sum(i["k"] for i in incs)
    n = sum(i["n"] for i in incs)
    tesla_n = sum(1 for i in incs if i["tesla"])
    rate = k / n * 100 if n else float("nan")
    print(f"{label}: incidents={len(incs)} (tesla={tesla_n}) articles={n} named={k} rate={rate:.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--min-outlets", type=int, default=2)
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    rows = load_rows(None, args.db)
    incidents, _ = to_incidents(rows, min_outlets=args.min_outlets)

    ooc = [i for i in incidents if is_out_of_control(db, i["incident_id"])]
    non_ooc = [i for i in incidents if not is_out_of_control(db, i["incident_id"])]

    print("=== Out-of-control / into-structure classification ===")
    summarize("All incidents", incidents)
    summarize("  Out-of-control (OOC)", ooc)
    summarize("  Not OOC", non_ooc)
    print()
    summarize("OOC — Tesla", [i for i in ooc if i["tesla"]])
    summarize("OOC — Non-Tesla", [i for i in ooc if not i["tesla"]])
    print()
    summarize("Non-OOC — Tesla", [i for i in non_ooc if i["tesla"]])
    summarize("Non-OOC — Non-Tesla", [i for i in non_ooc if not i["tesla"]])

    if any(i["tesla"] for i in ooc) and any(not i["tesla"] for i in ooc):
        obs, p = permutation_p(ooc)
        print(f"\nWithin-OOC-subgroup permutation p = {p:.4f} (n_incidents={len(ooc)})")

    print("\nTesla incidents:")
    for i in incidents:
        if i["tesla"]:
            print(f"  {i['incident_id']}: OOC={is_out_of_control(db, i['incident_id'])}, "
                  f"headline-names-make {i['k']}/{i['n']}")


if __name__ == "__main__":
    main()
