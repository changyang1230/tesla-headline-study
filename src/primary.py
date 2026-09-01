"""THE STUDY. Two conditional probabilities and a test of the difference.

    p(make in title | the car is a Tesla)
    p(make in title | the car is not a Tesla)

That is the whole question. Everything in `analysis.py` is an appendix that checks
whether the gap between these two numbers survives adjustment — useful if the gap looks
interesting, irrelevant if it does not exist.

Standard library only. The actual study runs on plain Python; pandas and statsmodels are
needed only for the appendix.

Usage:
    python -m src.primary --db data/study.db
    python -m src.primary --csv data/simulated.csv --out output/primary_simulated.md
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import math
import pathlib
import random
import sqlite3

#: Coverage threshold — an incident qualifies if at least this many of the top 10 brands
#: covered it (docs/OUTLETS.md § Threshold). Protocol §10.4 fallback invoked 2026-08-25:
#: 5 left only 15 eligible clusters, judged too few before any outcome comparison was
#: run. Dropped to 3 — see matching note in cluster_incidents.py and CLAUDE.md.
#: Dropped again to 2 on 2026-08-25, explicitly AFTER seeing the ≥3 result (1 Tesla
#: incident, p=0.085) vs. the ≥2 sensitivity number (2 Tesla incidents, p=0.0029) — this
#: is the exact post-hoc threshold-shopping the Analysis Integrity section otherwise
#: warns against, done anyway at the user's explicit, informed request: this is personal
#: research, not for publication, and they accepted the tradeoff knowingly. Not a
#: pre-specified decision — do not describe it as one. See CLAUDE.md's decision table.
MIN_OUTLETS = 2

N_PERMUTATIONS = 20000
PERMUTATION_SEED = 20260101


# --------------------------------------------------------------------- statistics

def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson score interval — behaves sensibly at 0 and at small n, unlike Wald."""
    if n == 0:
        return (float("nan"), float("nan"))
    p, z2 = k / n, z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe_diff(k1: int, n1: int, k0: int, n0: int) -> tuple[float, float]:
    """Newcombe's hybrid-score interval for a difference of two proportions."""
    l1, u1 = wilson(k1, n1)
    l0, u0 = wilson(k0, n0)
    p1, p0 = k1 / n1, k0 / n0
    lo = (p1 - p0) - math.sqrt((p1 - l1) ** 2 + (u0 - p0) ** 2)
    hi = (p1 - p0) + math.sqrt((u1 - p1) ** 2 + (p0 - l0) ** 2)
    return (max(-1.0, lo), min(1.0, hi))


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for [[a, b], [c, d]]. Stdlib; exact rational arithmetic."""
    n = a + b + c + d
    if n == 0:
        return float("nan")
    r1, c1 = a + b, a + c

    def prob(x: int) -> float:
        return (math.comb(r1, x) * math.comb(n - r1, c1 - x)) / math.comb(n, c1)

    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    observed = prob(a)
    # Sum tables no more likely than the observed one; the 1e-9 guard avoids dropping
    # ties to floating-point noise, which would understate the p-value.
    return min(1.0, sum(p for x in range(lo, hi + 1)
                        if (p := prob(x)) <= observed * (1 + 1e-9)))


def permutation_p(incidents: list[dict], n_perm: int = N_PERMUTATIONS,
                  seed: int = PERMUTATION_SEED) -> tuple[float, float]:
    """Cluster-safe p-value: permute the Tesla label across INCIDENTS, not articles.

    Articles within one incident are not independent — outlets copy each other, and
    whether the make is "the story" is mostly decided at the incident level. A test that
    treats 8 articles about one crash as 8 independent observations reports a p-value far
    smaller than the evidence supports.

    Permuting the label at the incident level keeps each incident's articles together, so
    the null distribution carries the real clustering. This is the honest p-value.
    """
    rng = random.Random(seed)
    labels = [i["tesla"] for i in incidents]

    def diff(labs) -> float:
        k1 = n1 = k0 = n0 = 0
        for inc, lab in zip(incidents, labs):
            if lab:
                k1 += inc["k"]; n1 += inc["n"]
            else:
                k0 += inc["k"]; n0 += inc["n"]
        if not n1 or not n0:
            return 0.0
        return k1 / n1 - k0 / n0

    observed = diff(labels)
    shuffled = list(labels)
    extreme = 0
    for _ in range(n_perm):
        rng.shuffle(shuffled)
        if abs(diff(shuffled)) >= abs(observed) - 1e-12:
            extreme += 1
    # add-one correction: a permutation p is never exactly 0
    return observed, (extreme + 1) / (n_perm + 1)


# ------------------------------------------------------------------------- loading

def load_rows(csv_path: str | None, db_path: str | None) -> list[dict]:
    if csv_path:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            return [dict(r) for r in csv.DictReader(fh)]
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT * FROM v_analysis")]
    con.close()
    return rows


def to_incidents(rows: list[dict], *, min_outlets: int = MIN_OUTLETS,
                 tier1_only: bool = False, require_known_make: bool = True
                 ) -> tuple[list[dict], dict]:
    """Collapse articles to incidents, applying the coverage threshold.

    `require_known_make` (default True) restricts the population to incidents where the
    vehicle's make is actually determined, for both arms. "Does the headline name the
    make" presupposes a make to name — an incident where no source ever established what
    car was involved isn't a case where the headline failed to name a known brand, it's a
    case where there's no ground truth to check the headline against. Mixing the two
    conflates "was the brand ever ascertained" with "did the headline surface it," which
    are different questions. Set False to reproduce the earlier (broader) population.
    """
    by_inc: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        by_inc[r["incident_id"]].append(r)

    kept, dropped = [], collections.Counter()
    for inc_id, arts in by_inc.items():
        if tier1_only and str(arts[0].get("make_tier", "")) != "1":
            dropped["tier 2 make (media-dependent)"] += 1
            continue
        if require_known_make and not arts[0].get("index_make"):
            dropped["make not established"] += 1
            continue
        outlets = {a.get("outlet") or a.get("outlet_group") for a in arts}
        if len(outlets) < min_outlets:
            dropped[f"covered by fewer than {min_outlets} outlets"] += 1
            continue
        k = sum(int(a["headline_names_make"]) for a in arts)
        kept.append({
            "incident_id": inc_id, "k": k, "n": len(arts),
            "tesla": int(arts[0]["tesla"]),
            "make": arts[0].get("index_make", ""),
            "prop": k / len(arts),
        })
    return kept, dict(dropped)


def ascertainment(db_path: str | None, *, start: str | None = None, end: str | None = None) -> dict:
    """How many incidents were lost because the make could not be determined?

    This is the denominator problem, and it deserves to be visible rather than implicit.
    For a Tesla, some outlet almost always says so. For a small hatchback, outlets often
    just write "a car" — so that incident silently leaves the study.

    The non-Tesla incidents that survive are therefore enriched for ones where somebody
    named the make, which correlates with naming it in a headline. That INFLATES
    p(title | non-Tesla) and makes the Tesla gap look smaller than it is. A positive
    finding survives this bias; a null finding cannot be interpreted without knowing how
    big the excluded pile was.
    """
    if not db_path:
        return {}
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    out: dict = {}
    # Scope to the study window when given — `incident` also holds leftover pre-pivot
    # incidents (see CLAUDE.md's Study period decision) that were never adjudicated and
    # would otherwise inflate "make undetermined" with rows this study period never
    # touched, not real ascertainment loss.
    where, params = "", ()
    if start and end:
        where, params = " WHERE incident_date >= ? AND incident_date <= ?", (start, end)
    try:
        out["total_incidents"] = con.execute(
            f"SELECT COUNT(*) FROM incident{where}", params).fetchone()[0]
        out["eligible"] = con.execute(
            f"SELECT COUNT(*) FROM incident{where}{' AND' if where else ' WHERE'} eligible=1",
            params).fetchone()[0]
        out["make_unknown"] = con.execute(
            f"SELECT COUNT(*) FROM incident{where}"
            f"{' AND' if where else ' WHERE'} (index_make IS NULL OR index_make='')",
            params).fetchone()[0]
        out["by_tier"] = {r[0]: r[1] for r in con.execute(
            f"SELECT make_tier, COUNT(*) FROM incident{where}"
            f"{' AND' if where else ' WHERE'} eligible=1 GROUP BY 1", params)}
    except sqlite3.Error:
        pass
    con.close()
    return out


# ------------------------------------------------------------------------- report

def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def build_report(incidents: list[dict], dropped: dict, asc: dict, label: str,
                 *, min_outlets: int, n_perm: int,
                 rows_for_sensitivity: list[dict] | None = None,
                 tier1_only: bool = False, require_known_make: bool = True) -> str:
    L: list[str] = []
    w = L.append

    tesla = [i for i in incidents if i["tesla"]]
    other = [i for i in incidents if not i["tesla"]]
    k1, n1 = sum(i["k"] for i in tesla), sum(i["n"] for i in tesla)
    k0, n0 = sum(i["k"] for i in other), sum(i["n"] for i in other)

    w(f"# Does the headline name the car? — {label}")
    w("")
    w(f"Generated {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}  ")
    w(f"Incidents covered by ≥{min_outlets} of the top 10 Australian news brands: "
      f"**{len(incidents)}** ({len(tesla)} Tesla, {len(other)} non-Tesla), "
      f"**{n1 + n0}** articles.")
    w("")

    if not tesla or not other:
        w("> Cannot compute the comparison — one of the two arms is empty.")
        return "\n".join(L)

    p1, p0 = k1 / n1, k0 / n0
    l1, u1 = wilson(k1, n1)
    l0, u0 = wilson(k0, n0)

    w("## The answer")
    w("")
    w("| | articles | headline names the make | **probability** | 95% CI |")
    w("|---|---|---|---|---|")
    w(f"| **Tesla** | {n1} | {k1} | **{pct(p1)}** | {pct(l1)} – {pct(u1)} |")
    w(f"| **Not Tesla** | {n0} | {k0} | **{pct(p0)}** | {pct(l0)} – {pct(u0)} |")
    w("")

    dlo, dhi = newcombe_diff(k1, n1, k0, n0)
    ratio = p1 / p0 if p0 else float("inf")
    w(f"**Difference: {pct(p1 - p0)}** (95% CI {pct(dlo)} – {pct(dhi)})  ")
    w(f"**Ratio: {ratio:.2f}×** — a Tesla's make is {ratio:.1f} times as likely to appear "
      f"in the headline.")
    w("")

    observed, perm_p = permutation_p(incidents, n_perm=n_perm)
    fisher_p = fisher_exact(k1, n1 - k1, k0, n0 - k0)
    w(f"**p = {perm_p:.4f}** (permutation test, Tesla label shuffled across incidents — "
      f"{n_perm:,} permutations)")
    w("")
    w(f"<sub>Fisher exact on the raw 2×2 gives p = {fisher_p:.2e}, but that treats eight "
      f"articles about one crash as eight independent facts. They are not — outlets copy "
      f"each other, and whether the make is 'the story' is settled at the incident level. "
      f"The permutation p above keeps each incident's articles together and is the one to "
      f"quote.</sub>")
    w("")

    # ---- incident level, the same question asked a second way
    w("## Same question, incident as the unit")
    w("")
    tp = sorted(i["prop"] for i in tesla)
    op = sorted(i["prop"] for i in other)
    med = lambda v: v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
    w("| | incidents | median share of covering outlets naming the make | mean |")
    w("|---|---|---|---|")
    w(f"| **Tesla** | {len(tesla)} | **{pct(med(tp))}** | {pct(sum(tp) / len(tp))} |")
    w(f"| **Not Tesla** | {len(other)} | **{pct(med(op))}** | {pct(sum(op) / len(op))} |")
    w("")
    all_named = lambda v: sum(1 for x in v if x >= 0.5)
    w(f"Named by at least half the covering outlets: "
      f"**{all_named(tp)}/{len(tp)}** Tesla incidents vs "
      f"**{all_named(op)}/{len(op)}** non-Tesla.")
    w("")

    # ---- per-make breakdown
    w("## By make")
    w("")
    by_make: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0, 0])
    for i in incidents:
        e = by_make[i["make"] or "(unknown)"]
        e[0] += 1; e[1] += i["k"]; e[2] += i["n"]
    w("| Make | incidents | articles | headline names the make |")
    w("|---|---|---|---|")
    for make, (ni, k, n) in sorted(by_make.items(), key=lambda kv: -kv[1][0]):
        w(f"| {make} | {ni} | {n} | {pct(k / n) if n else '—'} |")
    w("")
    w("Read this table before believing the headline number. If a premium make sits right "
      "next to Tesla, the effect may be about distinctive or expensive cars rather than "
      "about Tesla specifically — which is a different and more interesting finding.")
    w("")

    # ---- what got excluded
    w("## What did not make it in")
    w("")
    if dropped:
        w("| Reason | incidents dropped |")
        w("|---|---|")
        for reason, count in sorted(dropped.items(), key=lambda kv: -kv[1]):
            w(f"| {reason} | {count} |")
        w("")
    if asc:
        unknown = asc.get("make_unknown", 0)
        total = asc.get("total_incidents", 0)
        w(f"Candidate incidents: **{total}**; make could not be determined for "
          f"**{unknown}**"
          + (f" (**{100 * unknown / total:.0f}%**)" if total else "") + ".")
        tiers = asc.get("by_tier") or {}
        if tiers:
            w(f"Of the eligible incidents, make established from a media-independent "
              f"source (police / coronial / court): **{tiers.get(1, 0)}**; from article "
              f"text only: **{tiers.get(2, 0)}**.")
        w("")
        w("> **This is the denominator to worry about.** For a Tesla, some outlet almost "
          "always says so. For a small hatchback, outlets often just write \"a car\" — and "
          "that incident silently leaves the study. The non-Tesla incidents that survive "
          "are therefore enriched for ones where *somebody* named the make, which "
          "correlates with naming it in the headline. That pushes "
          "`p(title | non-Tesla)` **up**, making the gap look **smaller** than it is.")
        w(">")
        w("> So a positive result survives this bias. A null result does not, and cannot "
          "be interpreted without knowing how big that excluded pile was. Run "
          "`--tier1-only` to see the version that does not depend on article text at all.")
        w("")

    # ---- sensitivity: does the result depend on the ≥3-outlet coverage threshold?
    if rows_for_sensitivity is not None:
        w("## Sensitivity: coverage threshold")
        w("")
        w("Everything above only includes incidents covered by at least "
          f"**{min_outlets}** of the top 10 outlets — below that, an incident never enters "
          "the probability calculation, the confidence interval, or the permutation test; "
          "it only shows up as a count in \"What did not make it in\" above. That is an "
          "unexamined exclusion: if Tesla incidents clear the coverage bar more easily "
          "than non-Tesla incidents (plausible, since novelty is what got them covered at "
          "all — see the Severity decision in CLAUDE.md), the excluded pile is not a "
          "random sample and the threshold itself could be shaping the result. This "
          "reruns the same comparison at other thresholds, on the same underlying "
          "incident set, to check whether the effect's direction and rough size survive.")
        w("")
        w("| min outlets | incidents (Tesla / non-Tesla) | p(title \\| Tesla) | "
          "p(title \\| non-Tesla) | difference | permutation p |")
        w("|---|---|---|---|---|---|")
        for mo in sorted({1, 2, 3, min_outlets, 5}):
            sens_incidents, _ = to_incidents(rows_for_sensitivity, min_outlets=mo,
                                             tier1_only=tier1_only,
                                             require_known_make=require_known_make)
            st = [i for i in sens_incidents if i["tesla"]]
            so = [i for i in sens_incidents if not i["tesla"]]
            if not st or not so:
                w(f"| {mo} | {len(st)} / {len(so)} | — | — | — | one arm empty |")
                continue
            sk1, sn1 = sum(i["k"] for i in st), sum(i["n"] for i in st)
            sk0, sn0 = sum(i["k"] for i in so), sum(i["n"] for i in so)
            sp1, sp0 = sk1 / sn1, sk0 / sn0
            _, sperm_p = permutation_p(sens_incidents, n_perm=n_perm)
            flag = " ⟵ reported above" if mo == min_outlets else ""
            w(f"| {mo} | {len(st)} / {len(so)} | {pct(sp1)} | {pct(sp0)} | "
              f"{pct(sp1 - sp0)} | {sperm_p:.4f}{flag} |")
        w("")

    w("---")
    w("")
    w("### Reading this")
    w("")
    w("- These are probabilities about **headline writing**, not about vehicle safety. "
      "Nothing here says any car is more or less dangerous.")
    w("- Quote the permutation p, not the Fisher p.")
    w("- Check the by-make table before concluding this is about Tesla.")
    w("- `analysis.py` (appendix) adjusts for severity, incident type, vehicle age, "
      "jurisdiction and outlet, and runs the self-matched comparison within crashes "
      "involving a Tesla *and* another car. Worth running if the gap above is real; "
      "pointless if it is not.")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv")
    ap.add_argument("--db")
    ap.add_argument("--out", default="output/primary_result.md")
    ap.add_argument("--min-outlets", type=int, default=MIN_OUTLETS)
    ap.add_argument("--tier1-only", action="store_true",
                    help="restrict to incidents whose make came from a police, coronial "
                         "or court source rather than article text")
    ap.add_argument("--include-unknown-make", action="store_true",
                    help="include incidents where the make was never established "
                         "(reproduces the earlier, broader population; default excludes them)")
    ap.add_argument("--n-perm", type=int, default=N_PERMUTATIONS)
    ap.add_argument("--label", default=None)
    ap.add_argument("--start", default=None,
                    help="study window start, for the ascertainment denominator only — "
                         "e.g. 2025-09-01 (excludes leftover pre-pivot incidents from "
                         "'candidate incidents' / 'make undetermined' counts)")
    ap.add_argument("--end", default=None, help="study window end, e.g. 2026-08-31")
    args = ap.parse_args()

    if not (args.csv or args.db):
        raise SystemExit("give --csv or --db")
    rows = load_rows(args.csv, args.db)
    require_known_make = not args.include_unknown_make
    incidents, dropped = to_incidents(rows, min_outlets=args.min_outlets,
                                      tier1_only=args.tier1_only,
                                      require_known_make=require_known_make)
    label = args.label or ("simulated data" if args.csv and "simul" in args.csv
                           else "study dataset")
    if args.tier1_only:
        label += ", Tier 1 makes only"
    text = build_report(incidents, dropped,
                        ascertainment(args.db, start=args.start, end=args.end), label,
                        min_outlets=args.min_outlets, n_perm=args.n_perm,
                        rows_for_sensitivity=rows, tier1_only=args.tier1_only,
                        require_known_make=require_known_make)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[written to {out}]")


if __name__ == "__main__":
    main()
