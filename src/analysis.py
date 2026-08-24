"""APPENDIX analysis (Protocol section 9.1b). Run ONCE, after dataset lock.

**This is not the study.** The study is `src/primary.py`: two conditional probabilities
and a permutation test. Run that first.

What this adds is one question: does the gap between those two probabilities survive
adjustment for severity, incident type, vehicle age, jurisdiction, year and outlet — and
does it hold inside crashes that involved a Tesla *and* another car, where every
confounder is held constant by construction? Worth asking if there is a gap. Pointless if
there is not.

Everything in this file was written and debugged against `simulate.py` output before any
real data existed. That is what makes "pre-specified" mean something here: the model
formulae could not have been shaped by the real results.

Usage:
    python -m src.primary  --db data/study.db                    # <- the study
    python -m src.analysis --db data/study.db --out output/results.md   # <- the appendix

Any analysis not in this file at dataset-lock time is post-hoc and belongs in a
separately labelled section of the manuscript.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import pathlib
import sqlite3
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.genmod.families import Binomial
from statsmodels.genmod.cov_struct import Exchangeable, Independence
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*convergence.*")

#: Adjustment set (Protocol section 7.5). `remoteness` stands in for `state`: eight
#: state dummies would spend degrees of freedom this design cannot afford, and metro vs
#: regional is the axis that actually differs between the Tesla and non-Tesla fleets.
#: Mediators (adas_alleged, fire_involved) are deliberately absent — see section 9.5.
ADJUSTMENT = ("C(deaths_cat) + C(incident_type) + victim_child + year_c "
              "+ C(vehicle_age_band) + multi_vehicle + C(remoteness) + C(outlet_register)")

PRIMARY_OUTCOME = "headline_names_make"


# --------------------------------------------------------------------------- loading

def load(csv: str | None, db: str | None) -> pd.DataFrame:
    if csv:
        df = pd.read_csv(csv)
    elif db:
        con = sqlite3.connect(db)
        df = pd.read_sql_query("SELECT * FROM v_analysis", con)
        con.close()
    else:
        raise SystemExit("give --csv or --db")
    return prepare(df)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["deaths_cat"] = pd.cut(df["deaths"], bins=[-1, 0, 1, 99],
                              labels=["0", "1", "2+"]).astype(str)
    df["year_c"] = df["year"] - df["year"].mean()
    for c in ("vehicle_age_band", "remoteness", "outlet_register", "incident_type"):
        if c not in df:
            df[c] = "unknown"
        df[c] = df[c].fillna("unknown").astype(str)
    if "make_group" not in df:
        from .lexicon import MAKE_GROUP
        df["make_group"] = df["index_make"].map(MAKE_GROUP).fillna("mainstream_ice")
    df["tesla"] = (df["index_make"] == "Tesla").astype(int)
    df["toyota"] = (df["index_make"] == "Toyota").astype(int)
    for c in ("multi_vehicle", "victim_child", "is_wire", "adas_alleged", "fire_involved"):
        if c in df:
            df[c] = df[c].fillna(0).astype(int)
    return df


# ----------------------------------------------------------------------- estimation

def gee_fit(df: pd.DataFrame, outcome: str, exposure: str, *, adjust: bool = True,
            cov=None):
    formula = f"{outcome} ~ {exposure}" + (f" + {ADJUSTMENT}" if adjust else "")
    model = smf.gee(formula, groups="incident_id", data=df,
                    family=Binomial(), cov_struct=cov or Exchangeable())
    return model.fit(maxiter=100)


def effect(res, term: str) -> dict[str, float]:
    b = res.params[term]
    se = res.bse[term]
    ci = res.conf_int().loc[term]
    return {"or": float(np.exp(b)), "lo": float(np.exp(ci[0])), "hi": float(np.exp(ci[1])),
            "beta": float(b), "se": float(se), "p": float(res.pvalues[term])}


def cluster_bootstrap(df: pd.DataFrame, outcome: str, exposure: str,
                      n_boot: int = 1000, seed: int = 20260101,
                      adjust: bool = True) -> tuple[float, float, int]:
    """Percentile CI from resampling incidents with replacement (Protocol section 9.1).

    Refits with an independence working correlation: the bootstrap itself supplies the
    clustering, and the point estimate stays consistent. Reported as the primary interval
    when the number of incidents is small, where sandwich SEs are known to be optimistic.
    """
    rng = np.random.default_rng(seed)
    incidents = df["incident_id"].unique()
    by_inc = {i: g for i, g in df.groupby("incident_id")}
    formula = f"{outcome} ~ {exposure}" + (f" + {ADJUSTMENT}" if adjust else "")
    ests, failed = [], 0
    for _ in range(n_boot):
        pick = rng.choice(incidents, size=len(incidents), replace=True)
        boot = pd.concat([by_inc[i].assign(incident_id=f"{i}_{k}")
                          for k, i in enumerate(pick)], ignore_index=True)
        try:
            r = smf.glm(formula, data=boot, family=Binomial()).fit()
            ests.append(r.params[exposure])
        except Exception:
            failed += 1
    if len(ests) < n_boot * 0.5:
        return float("nan"), float("nan"), failed
    lo, hi = np.percentile(ests, [2.5, 97.5])
    return float(np.exp(lo)), float(np.exp(hi)), failed


def fmt(e: dict[str, float], *, boot: tuple[float, float] | None = None) -> str:
    s = f"OR {e['or']:.2f} (95% CI {e['lo']:.2f}–{e['hi']:.2f}), p = {e['p']:.4f}"
    if boot and not np.isnan(boot[0]):
        s += f"; cluster-bootstrap CI {boot[0]:.2f}–{boot[1]:.2f}"
    return s


# ----------------------------------------------------------------------- components

def to_markdown(df: pd.DataFrame) -> str:
    """Minimal markdown table writer — avoids a `tabulate` dependency for one table."""
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(r[c]) else str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def table_one(df: pd.DataFrame) -> pd.DataFrame:
    inc = df.groupby("incident_id").first()
    rows = []
    for grp, g in inc.groupby("make_group"):
        arts = df[df.incident_id.isin(g.index)]
        rows.append({
            "make_group": grp,
            "incidents": len(g),
            "articles": len(arts),
            "articles/incident": round(len(arts) / len(g), 1),
            "deaths (mean)": round(g["deaths"].mean(), 2),
            "child victim %": round(100 * g["victim_child"].mean(), 1),
            "multi-vehicle %": round(100 * g["multi_vehicle"].mean(), 1),
            "vehicle <=2y %": round(100 * (g["vehicle_age_band"] == "<=2y").mean(), 1),
            "metro %": round(100 * (g["remoteness"] == "metro").mean(), 1),
            "tier 1 make %": round(100 * (g["make_tier"] == 1).mean(), 1) if "make_tier" in g else np.nan,
            "HEADLINE NAMES MAKE %": round(100 * arts[PRIMARY_OUTCOME].mean(), 1),
            "body names make %": round(100 * arts["body_names_make"].mean(), 1)
                                  if "body_names_make" in arts else np.nan,
        })
    return pd.DataFrame(rows).sort_values("make_group")


def within_incident(df: pd.DataFrame) -> dict:
    """Self-matched analysis (Protocol section 9.3).

    Restricted to multi-vehicle incidents with a Tesla and one identified non-Tesla make.
    Each ARTICLE is a matched set: it either names the Tesla, the other make, both, or
    neither. Everything that confounds the between-incident comparison — severity,
    location, date, outlet, journalist — is held constant, because both makes are
    competing for the same headline.
    """
    need = {"second_make", "headline_names_second_make"}
    if not need <= set(df.columns):
        return {"n_articles": 0, "note": "columns absent"}
    sub = df[(df.tesla == 1) & (df.multi_vehicle == 1)
             & df.second_make.astype(str).str.len().gt(0)].copy()
    if sub.empty:
        return {"n_articles": 0, "note": "no eligible multi-vehicle Tesla incidents"}

    a = int(((sub[PRIMARY_OUTCOME] == 1) & (sub.headline_names_second_make == 1)).sum())
    b = int(((sub[PRIMARY_OUTCOME] == 1) & (sub.headline_names_second_make == 0)).sum())
    c = int(((sub[PRIMARY_OUTCOME] == 0) & (sub.headline_names_second_make == 1)).sum())
    d = int(((sub[PRIMARY_OUTCOME] == 0) & (sub.headline_names_second_make == 0)).sum())
    mc = mcnemar([[a, b], [c, d]], exact=True)

    out = {"n_incidents": int(sub.incident_id.nunique()), "n_articles": len(sub),
           "both": a, "tesla_only": b, "other_only": c, "neither": d,
           "p_exact": float(mc.pvalue),
           "or_matched": (b / c) if c else float("inf") if b else float("nan")}

    # conditional logistic on the same matched sets, for a model-based interval
    long = pd.concat([
        sub.assign(named=sub[PRIMARY_OUTCOME], is_tesla=1),
        sub.assign(named=sub.headline_names_second_make, is_tesla=0),
    ], ignore_index=True)
    try:
        cl = sm.ConditionalLogit(long["named"], long[["is_tesla"]],
                                 groups=long["article_id"]).fit(disp=0)
        ci = cl.conf_int().loc["is_tesla"]
        out.update({"clogit_or": float(np.exp(cl.params["is_tesla"])),
                    "clogit_lo": float(np.exp(ci[0])), "clogit_hi": float(np.exp(ci[1])),
                    "clogit_p": float(cl.pvalues["is_tesla"])})
    except Exception as exc:
        out["clogit_error"] = str(exc)
    return out


def incident_level(df: pd.DataFrame) -> dict:
    """Incident as the unit: proportion of covering articles naming the make."""
    g = df.groupby("incident_id").agg(
        k=(PRIMARY_OUTCOME, "sum"), n=(PRIMARY_OUTCOME, "size"),
        tesla=("tesla", "first"), deaths_cat=("deaths_cat", "first"),
        incident_type=("incident_type", "first"), victim_child=("victim_child", "first"),
        year_c=("year_c", "first"), vehicle_age_band=("vehicle_age_band", "first"),
        multi_vehicle=("multi_vehicle", "first"), remoteness=("remoteness", "first"),
    ).reset_index()
    g["prop"] = g.k / g.n
    g["failures"] = g.n - g.k
    t, o = g[g.tesla == 1]["prop"], g[g.tesla == 0]["prop"]
    u = stats.mannwhitneyu(t, o, alternative="two-sided")
    out = {"median_tesla": float(t.median()), "median_other": float(o.median()),
           "mean_tesla": float(t.mean()), "mean_other": float(o.mean()),
           "mwu_p": float(u.pvalue), "n_tesla": int(len(t)), "n_other": int(len(o))}
    formula = ("k + failures ~ tesla + C(deaths_cat) + C(incident_type) + victim_child "
               "+ year_c + C(vehicle_age_band) + multi_vehicle + C(remoteness)")
    try:
        r = smf.glm(formula, data=g, family=Binomial()).fit(scale="X2")  # quasi-binomial
        if r.scale < 1.0:
            # Underdispersion shrinks the standard errors below the binomial ones, which
            # would overstate precision. Floor the scale at 1 rather than take the credit.
            r = smf.glm(formula, data=g, family=Binomial()).fit(scale=1.0)
        ci = r.conf_int().loc["tesla"]
        out.update({"qb_or": float(np.exp(r.params["tesla"])),
                    "qb_lo": float(np.exp(ci[0])), "qb_hi": float(np.exp(ci[1])),
                    "qb_p": float(r.pvalues["tesla"]), "dispersion": float(r.scale)})
    except Exception as exc:
        out["qb_error"] = str(exc)
    return out


def icc(df: pd.DataFrame) -> float:
    """Exchangeable working correlation from the unadjusted GEE — the ICC the power
    calculation assumed. Report it: it is the number Phase 0 was meant to pin down."""
    try:
        res = gee_fit(df, PRIMARY_OUTCOME, "tesla", adjust=False)
        return float(res.cov_struct.dep_params)
    except Exception:
        return float("nan")


# ------------------------------------------------------------------------- reporting

def run(df: pd.DataFrame, n_boot: int, out_path: pathlib.Path, label: str) -> None:
    buf = io.StringIO()
    w = lambda *a: print(*a, file=buf)

    n_inc = df.incident_id.nunique()
    n_tesla_inc = int(df.groupby("incident_id").tesla.first().sum())

    w(f"# Appendix results — {label}")
    w()
    w("> **This is the appendix.** The study's result is in `output/primary_result.md` "
      "(`python -m src.primary`): two conditional probabilities and a permutation test. "
      "What follows asks only whether that gap survives adjustment.")
    w()
    w(f"Generated {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}  ")
    w(f"Articles: **{len(df)}** across **{n_inc}** incidents "
      f"(**{n_tesla_inc}** Tesla, {n_inc - n_tesla_inc} non-Tesla)")
    w()
    w("> Pre-specified in PROTOCOL.md section 9. Anything not in `src/analysis.py` at "
      "dataset lock is post-hoc and must be labelled as such.")
    w()

    w("## Table 1 — incidents and coverage by make group")
    w()
    w(to_markdown(table_one(df)))
    w()

    rho = icc(df)
    w(f"Estimated intracluster correlation (exchangeable working correlation): "
      f"**{rho:.3f}**. The power calculation assumed 0.50; "
      f"`python -m src.power --rho {rho:.2f}` re-derives the requirement.")
    w()

    # ---- primary
    w("## Primary analysis — Tesla vs all other makes")
    w()
    res = gee_fit(df, PRIMARY_OUTCOME, "tesla")
    e = effect(res, "tesla")
    boot = cluster_bootstrap(df, PRIMARY_OUTCOME, "tesla", n_boot=n_boot)
    w(f"Adjusted GEE (exchangeable, clustered on incident, robust SE): **{fmt(e, boot=boot[:2])}**")
    if boot[2]:
        w(f"({boot[2]} of {n_boot} bootstrap refits failed to converge and were dropped.)")
    w()
    unadj = effect(gee_fit(df, PRIMARY_OUTCOME, "tesla", adjust=False), "tesla")
    w(f"Unadjusted: {fmt(unadj)}")
    w()
    w(f"Interpretation: the adjusted odds that a headline identifies the vehicle's make "
      f"are {'higher' if e['or'] > 1 else 'lower'} for Tesla by a factor of "
      f"{e['or']:.2f}. This is a statement about **editorial behaviour**, not about "
      f"vehicle safety.")
    w()

    # ---- incident-level companion
    il = incident_level(df)
    w("## Incident-level companion analysis")
    w()
    w(f"Median proportion of covering articles naming the make: "
      f"Tesla **{il['median_tesla']:.2f}** (n={il['n_tesla']}) vs "
      f"other **{il['median_other']:.2f}** (n={il['n_other']}); "
      f"Mann–Whitney p = {il['mwu_p']:.4f}")
    if "qb_or" in il:
        w(f"Adjusted quasi-binomial GLM: OR {il['qb_or']:.2f} "
          f"(95% CI {il['qb_lo']:.2f}–{il['qb_hi']:.2f}), p = {il['qb_p']:.4f} "
          f"(dispersion {il['dispersion']:.2f})")
    w()

    # ---- secondaries (Holm across the three pre-specified)
    w("## Secondary objectives (Holm-adjusted family of three)")
    w()
    sec = {}
    for name, mask in [
        ("Tesla vs other BEV", df.make_group.isin(["tesla", "other_bev"])),
        ("Tesla vs premium ICE", df.make_group.isin(["tesla", "premium_ice"])),
    ]:
        sub = df[mask]
        if sub.tesla.nunique() < 2 or len(sub) < 30:
            sec[name] = None
            continue
        try:
            sec[name] = effect(gee_fit(sub, PRIMARY_OUTCOME, "tesla"), "tesla")
        except Exception as exc:
            sec[name] = {"error": str(exc)}

    wi = within_incident(df)
    rows, praw = [], []
    for name, e2 in sec.items():
        if e2 and "or" in e2:
            rows.append([name, f"{e2['or']:.2f}", f"{e2['lo']:.2f}–{e2['hi']:.2f}", e2["p"]])
            praw.append(e2["p"])
        else:
            rows.append([name, "—", "—", np.nan])
    if wi.get("n_articles"):
        rows.append(["Within-incident (matched)",
                     f"{wi.get('clogit_or', wi['or_matched']):.2f}",
                     f"{wi.get('clogit_lo', float('nan')):.2f}–{wi.get('clogit_hi', float('nan')):.2f}",
                     wi["p_exact"]])
        praw.append(wi["p_exact"])
    else:
        rows.append(["Within-incident (matched)", "—", "—", np.nan])

    valid = [p for p in praw if not np.isnan(p)]
    adj = dict(zip([i for i, p in enumerate(praw) if not np.isnan(p)],
                   multipletests(valid, method="holm")[1])) if valid else {}
    w("| Contrast | OR | 95% CI | p (raw) | p (Holm) |")
    w("|---|---|---|---|---|")
    for i, r in enumerate(rows):
        praw_s = "—" if np.isnan(r[3]) else f"{r[3]:.4f}"
        padj_s = "—" if i not in adj else f"{adj[i]:.4f}"
        w(f"| {r[0]} | {r[1]} | {r[2]} | {praw_s} | {padj_s} |")
    w()
    if wi.get("n_articles"):
        w(f"**Within-incident detail** — {wi['n_incidents']} multi-vehicle incidents "
          f"involving a Tesla and one other identified make, {wi['n_articles']} articles. "
          f"Named both: {wi['both']}; Tesla only: **{wi['tesla_only']}**; "
          f"other make only: **{wi['other_only']}**; neither: {wi['neither']}. "
          f"McNemar exact p = {wi['p_exact']:.4f}.")
        w()
        w("This is the comparison least vulnerable to confounding, because both makes are "
          "in the same crash competing for the same headline. If it disagrees with the "
          "primary analysis, it is the finding, not a footnote (Protocol section 9.3).")
    else:
        w(f"Within-incident analysis not estimable: {wi.get('note', 'insufficient data')}.")
    w()

    # ---- negative controls
    w("## Negative controls (Protocol section 9.4)")
    w()
    if "body_names_make" in df:
        eb = effect(gee_fit(df, "body_names_make", "tesla"), "tesla")
        w(f"**Outcome control** — make named anywhere in the body: {fmt(eb)}")
        w()
        w("A large headline effect with a null body effect points to headline-specific "
          "salience. Similar effects on both would instead suggest the Tesla was simply "
          "easier to identify, which is a different claim.")
        w()
    nont = df[df.tesla == 0]
    if nont.toyota.sum() > 0 and nont.toyota.nunique() > 1:
        try:
            et = effect(gee_fit(nont, PRIMARY_OUTCOME, "toyota"), "toyota")
            w(f"**Exposure control** — Toyota vs other non-Tesla makes: {fmt(et)}")
            w()
            w("Toyota is the highest-volume make on Australian roads with no salience "
              "narrative attached. A large effect here would mean the model is picking up "
              "something other than brand salience.")
        except Exception as exc:
            w(f"**Exposure control** — not estimable ({exc}).")
    w()

    # ---- sensitivity
    w("## Sensitivity analyses")
    w()
    w("| Analysis | Rationale | OR | 95% CI | p |")
    w("|---|---|---|---|---|")

    def srow(name, why, frame, outcome=PRIMARY_OUTCOME, cov=None, adjust=True):
        try:
            e2 = effect(gee_fit(frame, outcome, "tesla", cov=cov, adjust=adjust), "tesla")
            w(f"| {name} | {why} | {e2['or']:.2f} | {e2['lo']:.2f}–{e2['hi']:.2f} | {e2['p']:.4f} |")
        except Exception as exc:
            w(f"| {name} | {why} | — | — | not estimable ({type(exc).__name__}) |")

    if "make_tier" in df:
        srow("Tier 1 make only", "removes media-dependent make ascertainment (§7.2)",
             df[df.make_tier == 1])
    if "headline_names_make_strict" in df:
        srow("Make token only", "excludes model tokens from the outcome (§7.3)",
             df, outcome="headline_names_make_strict")
    if "syndication_group_id" in df:
        dedup = df[(df.syndication_group_id.isna()) | (df.syndication_group_id.astype(str) == "")]
        extra = (df[~df.index.isin(dedup.index)]
                 .drop_duplicates(subset=["incident_id", "syndication_group_id"]))
        srow("One article per wire group", "removes syndicated duplication (§8.4)",
             pd.concat([dedup, extra], ignore_index=True))
    if "is_wire" in df:
        srow("Excluding wire copy", "original reporting only", df[df.is_wire == 0])
    srow("Independence working correlation", "GEE working-structure robustness",
         df, cov=Independence())
    srow("Unadjusted", "no covariate adjustment", df, adjust=False)
    w()

    # ---- mediation-flavoured
    if {"adas_alleged", "fire_involved"} <= set(df.columns):
        w("## Mediator-adjusted model (Protocol section 9.5 — descriptive only)")
        w()
        try:
            f = (f"{PRIMARY_OUTCOME} ~ tesla + adas_alleged + fire_involved + {ADJUSTMENT}")
            rm = smf.gee(f, groups="incident_id", data=df, family=Binomial(),
                         cov_struct=Exchangeable()).fit(maxiter=100)
            em = effect(rm, "tesla")
            w(f"Adding the self-driving and fire narratives: {fmt(em)} "
              f"(primary was OR {e['or']:.2f}).")
            w()
            w("Reported descriptively. These are mediators, not confounders, so this is "
              "*not* a better-adjusted estimate — it shows how much of the association "
              "travels with those two narratives. Formal mediation identification "
              "assumptions are not met here.")
        except Exception as exc:
            w(f"Not estimable ({exc}).")
        w()

    # ---- subgroups
    w("## Subgroups (exploratory, unadjusted for multiplicity)")
    w()
    w("| Subgroup | n articles | OR | 95% CI | p |")
    w("|---|---|---|---|---|")
    for col in ("outlet_register", "incident_type", "remoteness"):
        if col not in df:
            continue
        for lvl, g in df.groupby(col):
            if g.tesla.nunique() < 2 or len(g) < 40 or g.groupby("incident_id").tesla.first().sum() < 5:
                continue
            try:
                e2 = effect(gee_fit(g, PRIMARY_OUTCOME, "tesla", adjust=False), "tesla")
                w(f"| {col} = {lvl} | {len(g)} | {e2['or']:.2f} | "
                  f"{e2['lo']:.2f}–{e2['hi']:.2f} | {e2['p']:.4f} |")
            except Exception:
                w(f"| {col} = {lvl} | {len(g)} | — | — | not estimable |")
    w()
    w("Hypothesis-generating only. No multiplicity control applied, and with this many "
      "strata some interval will exclude 1 by chance.")
    w()

    w("---")
    w()
    w("### Reading these numbers")
    w()
    w("- The estimand is a contrast of **editorial behaviour**: whether a headline names "
      "the make. It says nothing about whether any vehicle is more or less safe, and the "
      "manuscript must say so in the title and abstract.")
    w("- The comparison is observational. Makes are not randomly assigned to crashes, and "
      "the adjustment set is an assumption (Protocol Appendix A), not a guarantee.")
    w("- If the Tier-1-only sensitivity analysis differs materially from the primary "
      "estimate, believe the Tier-1 one and say so.")
    w("- Report the interval, not the p-value, as the finding.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(buf.getvalue(), encoding="utf-8")
    print(buf.getvalue())
    print(f"\n[written to {out_path}]")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv")
    ap.add_argument("--db")
    ap.add_argument("--out", default="output/results.md")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    df = load(args.csv, args.db)
    label = args.label or ("simulated data" if args.csv and "simul" in args.csv
                           else "locked study dataset")
    run(df, args.n_boot, pathlib.Path(args.out), label)


if __name__ == "__main__":
    main()
