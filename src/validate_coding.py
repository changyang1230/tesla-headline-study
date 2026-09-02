"""Validate LLM-assisted coding against a hand-coded gold standard (lean-track 8.2).

LLM coding is only admissible if its error rate is known AND non-differential. The second
condition is the one that matters here and it is easy to miss:

    If Claude identifies Teslas from article text more reliably than it identifies
    Mazdas, then Tesla incidents enter the study with better make ascertainment than
    everything else. That is differential misclassification on the exposure, pointing in
    the same direction as the hypothesis, and it would produce a Tesla "effect" out of
    nothing but the coder.

So this module reports two things: overall agreement per variable, and a per-make
ascertainment table with an explicit Tesla-vs-rest differential. A high overall kappa
with a lopsided differential is a FAIL, not a pass.

Workflow:
    1. Hand-code 25-30 incidents into the `incident` table yourself, blind to the
       machine coding (do not read it first — that is the whole point).
    2. Mark them: UPDATE incident SET notes = notes || ' [GOLD]' WHERE ...
       or pass --gold-ids.
    3. python -m src.validate_coding --db data/study.db

Usage:
    python -m src.validate_coding --db data/study.db
    python -m src.validate_coding --db data/study.db --gold-csv output/gold_standard.csv
"""

from __future__ import annotations

import argparse
import collections
import csv
import logging
import pathlib
import sqlite3

LOG = logging.getLogger("validate_coding")

#: Variables checked, with the agreement statistic appropriate to each.
CATEGORICAL = ("state", "incident_type", "index_make", "second_make")
BOOLEAN = ("victim_child", "multi_vehicle", "fire_involved", "adas_alleged", "driver_notable")
NUMERIC = ("deaths", "serious_injuries")

#: Thresholds. index_make is the exposure variable, so it is held to a higher bar than
#: anything else — an error there misclassifies the comparison itself.
THRESHOLDS = {"index_make": 0.90, "_default_kappa": 0.70, "_default_exact": 0.85}

#: The differential that would invalidate the whole approach. If Tesla recall exceeds
#: non-Tesla recall by more than this, machine coding of index_make is not usable.
MAX_ASCERTAINMENT_DIFFERENTIAL = 0.10


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for two raters over categorical labels. None if undefined."""
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    a_counts = collections.Counter(a for a, _ in pairs)
    b_counts = collections.Counter(b for _, b in pairs)
    expected = sum((a_counts[k] / n) * (b_counts[k] / n)
                   for k in set(a_counts) | set(b_counts))
    if expected >= 1.0:
        return None  # every label identical; kappa undefined, report exact agreement
    return (observed - expected) / (1 - expected)


def _norm(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return {"True": "1", "False": "0", "true": "1", "false": "0", "None": ""}.get(s, s)


def load_machine(db: sqlite3.Connection) -> dict[str, dict[str, str]]:
    """All coders, not just 'claude' — `index_make` in particular is often resolved by
    the mechanical regex shortcut (`llm_coding.py`'s `store_mechanical`), which never
    touches the other Codebook fields. Restricting this to coder='claude' would silently
    treat every mechanically-coded incident as "the machine didn't answer," understating
    recall for whichever makes happen to route through the mechanical path more often —
    found 2026-08-26 when a real Tesla-vs-rest differential (-0.28, apparently a fail)
    turned out to be entirely an artifact of 2 of 3 gold Tesla incidents being
    mechanically coded and therefore invisible here; the correct, coder-inclusive
    differential was +0.08, a pass. An incident's index_make comes from exactly one
    coder (mechanical short-circuits before the LLM call), so there's no risk of one
    unit_id/variable pair getting two conflicting values here."""
    out: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for unit_id, var, val in db.execute(
            "SELECT unit_id, variable, value FROM dual_coding WHERE unit_type='incident'"):
        out[unit_id][var] = _norm(val)
    return out


def load_gold(db: sqlite3.Connection, gold_ids: list[str] | None,
              gold_csv: str | None) -> dict[str, dict[str, str]]:
    if gold_csv:
        with open(gold_csv, newline="", encoding="utf-8") as fh:
            return {r["incident_id"]: {k: _norm(v) for k, v in r.items()}
                    for r in csv.DictReader(fh)}
    db.row_factory = sqlite3.Row
    q = "SELECT * FROM incident"
    params: tuple = ()
    if gold_ids:
        q += f" WHERE incident_id IN ({','.join('?' * len(gold_ids))})"
        params = tuple(gold_ids)
    else:
        q += " WHERE notes LIKE '%[GOLD]%'"
    return {r["incident_id"]: {k: _norm(r[k]) for k in r.keys()} for r in db.execute(q, params)}


def ascertainment_table(gold: dict, machine: dict) -> list[dict]:
    """Per-make: how often did the machine recover the true make from body text?"""
    by_make: dict[str, list[bool]] = collections.defaultdict(list)
    for inc, g in gold.items():
        truth = g.get("index_make", "")
        if not truth:
            continue
        got = machine.get(inc, {}).get("index_make", "")
        by_make[truth].append(got == truth)
    rows = []
    for make, hits in sorted(by_make.items(), key=lambda kv: -len(kv[1])):
        rows.append({"make": make, "n": len(hits), "recovered": sum(hits),
                     "recall": sum(hits) / len(hits)})
    return rows


def report(gold: dict, machine: dict) -> tuple[str, bool]:
    lines, passed = [], True
    shared = sorted(set(gold) & set(machine))
    lines.append(f"# LLM coding validation\n")
    lines.append(f"Gold-standard incidents: **{len(gold)}**; machine-coded: **{len(machine)}**; "
                 f"overlapping (used): **{len(shared)}**\n")
    if len(shared) < 20:
        lines.append(f"> ⚠️ Only {len(shared)} overlapping incidents. Agreement statistics on "
                     f"fewer than 20 are too noisy to license the approach — hand-code more "
                     f"before relying on this.\n")

    lines.append("## Per-variable agreement\n")
    lines.append("| Variable | n | exact agreement | kappa | threshold | verdict |")
    lines.append("|---|---|---|---|---|---|")
    for var in CATEGORICAL + BOOLEAN + NUMERIC:
        pairs = [(gold[i].get(var, ""), machine[i].get(var, "")) for i in shared
                 if gold[i].get(var, "") or machine[i].get(var, "")]
        if not pairs:
            lines.append(f"| {var} | 0 | — | — | — | no data |")
            continue
        exact = sum(1 for a, b in pairs if a == b) / len(pairs)
        k = cohens_kappa(pairs) if var in CATEGORICAL + BOOLEAN else None
        thr = THRESHOLDS.get(var, THRESHOLDS["_default_kappa"] if k is not None
                             else THRESHOLDS["_default_exact"])
        metric = k if k is not None else exact
        ok = metric >= thr
        passed &= ok
        lines.append(f"| {var} | {len(pairs)} | {exact:.2f} | "
                     f"{'—' if k is None else f'{k:.2f}'} | {thr:.2f} | "
                     f"{'pass' if ok else '**FAIL**'} |")
    lines.append("")

    lines.append("## Make ascertainment by make — the differential check\n")
    rows = ascertainment_table(gold, machine)
    if not rows:
        lines.append("No gold-standard makes to compare.\n")
        return "\n".join(lines), False
    lines.append("| Make | gold incidents | make recovered | recall |")
    lines.append("|---|---|---|---|")
    for r in rows:
        lines.append(f"| {r['make']} | {r['n']} | {r['recovered']} | {r['recall']:.2f} |")
    lines.append("")

    tesla = [r for r in rows if r["make"] == "Tesla"]
    rest_n = sum(r["n"] for r in rows if r["make"] != "Tesla")
    rest_hit = sum(r["recovered"] for r in rows if r["make"] != "Tesla")
    if tesla and rest_n:
        t_recall, r_recall = tesla[0]["recall"], rest_hit / rest_n
        diff = t_recall - r_recall
        ok = abs(diff) <= MAX_ASCERTAINMENT_DIFFERENTIAL
        passed &= ok
        lines.append(f"**Tesla recall {t_recall:.2f} (n={tesla[0]['n']}) vs "
                     f"non-Tesla recall {r_recall:.2f} (n={rest_n}); "
                     f"differential {diff:+.2f}** — "
                     f"{'within' if ok else '**EXCEEDS**'} the "
                     f"{MAX_ASCERTAINMENT_DIFFERENTIAL:+.2f} limit.\n")
        if not ok:
            lines.append("> This is the failure that matters. The machine coder recovers the "
                         "make from body text at different rates for Tesla and everything "
                         "else, so Tesla incidents would enter the study with systematically "
                         "better exposure ascertainment. Do not proceed on machine-coded "
                         "`index_make`: hand-code the exposure for every incident, or restrict "
                         "the analysis to Tier 1 makes where the source is a police or "
                         "coronial document rather than article text.\n")
    else:
        lines.append("> Not enough Tesla incidents in the gold standard to compute the "
                     "differential. This check is not optional — hand-code more Tesla "
                     "incidents before relying on machine coding of the exposure.\n")
        passed = False

    lines.append("## Verdict\n")
    lines.append(f"**{'PASS' if passed else 'FAIL'}** — "
                 + ("machine coding may be used for the flagged-then-adjudicated workflow."
                    if passed else
                    "machine coding is not yet admissible for the failing variables. "
                    "Revise the extraction prompt or hand-code those variables."))
    return "\n".join(lines), passed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/study.db")
    ap.add_argument("--gold-ids", nargs="*", default=None)
    ap.add_argument("--gold-csv", default=None)
    ap.add_argument("--out", default="output/coding_validation.md")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    db = sqlite3.connect(args.db)
    gold = load_gold(db, args.gold_ids, args.gold_csv)
    machine = load_machine(db)
    if not gold:
        raise SystemExit("no gold-standard incidents found — mark them with [GOLD] in "
                         "incident.notes, or pass --gold-ids / --gold-csv")
    text, passed = report(gold, machine)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[written to {out}]")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
