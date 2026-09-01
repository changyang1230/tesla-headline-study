# The Tesla Headline Study

> Are Australian news headlines more likely to name the vehicle's make when the vehicle
> is a Tesla?

A research project testing an intuition: that media reports name "Tesla" in the headline
of vehicle-incident stories more readily than they name other makes. The intuition comes
from memorable examples, which is exactly what a salience effect would produce — so the
impression cannot be evidence for itself. This project is the design that can tell the
two apart.

**Status: complete.** The pipeline has run end to end on real data — a 12-month window
of Australian crash coverage (September 2025–August 2026). **Read the write-up:
[changyang1230.github.io/tesla-headline-study](https://changyang1230.github.io/tesla-headline-study/)**
— the full methodology, results, and robustness checks — with the [data
appendix](https://changyang1230.github.io/tesla-headline-study/appendix.html) behind it:
every incident, every headline, every source link.

**The headline result:** across 104 eligible, multi-outlet-covered crash incidents (3
involving a Tesla), headlines named the vehicle's make in **57.1%** of Tesla-related
articles versus **2.4%** of articles about other makes (permutation test clustered by
incident, p = 0.0003; clustered logistic regression odds ratio 64.15). The effect
survives checks against a general luxury-brand effect, single-outlet house style, and a
"dramatic out-of-control crash" alternative explanation — see the write-up for all of
them, and for the honest caveats (the whole result rests on 3 Tesla incidents; read the
confidence intervals, not just the headline percentages).

**Track: lean** — personal research, done properly. The design integrity stays (brand-blind
frame, freeze before extraction, pre-specified primary analysis); the journal machinery does not.
`PROTOCOL.md` §0 states exactly which is which. This is **not peer-reviewed** and should
be read as a well-supported, transparent first look, not a definitive finding.

| Document | What it is |
|---|---|
| [Write-up](https://changyang1230.github.io/tesla-headline-study/) | The result, methodology, and robustness checks. **Start here.** |
| [Data appendix](https://changyang1230.github.io/tesla-headline-study/appendix.html) | Every eligible incident, every headline, every source link. |
| [`PROTOCOL.md`](PROTOCOL.md) | The study design as originally pre-registered. |
| [`CODEBOOK.md`](CODEBOOK.md) | Every variable definition and coding rule, including the index-vehicle rules. |
| [`docs/OUTLETS.md`](docs/OUTLETS.md) | The outlet list, ranked by readership, with coverage-gap notes. |
| [`docs/SEED_EXAMPLES.md`](docs/SEED_EXAMPLES.md) | The motivating cases — excluded from the analysis, and why. |

## The design in one paragraph

Harvest a full year of Australian vehicle-incident coverage using a query set that
**contains no brand names**. Cluster the articles into incidents. Have a human adjudicate
every candidate incident, blind to the machine-suggested make where possible. Then, for
every article, ask one mechanical question: does the headline identify the make? Compare
Tesla incidents with everything else using an incident-clustered permutation test — the
primary result — with a GEE-based appendix and several post-hoc robustness checks (luxury
brand, single-outlet sensitivity, "dramatic crash" narrative type) behind it.

## The one thing that could sink this study

If incidents are discovered by searching for crashes, Tesla crashes surface more readily
*because the brand is in the headline*. The exposed and unexposed groups would then be
selected by the outcome, and any result would be circular.

Everything about the sampling frame exists to prevent that:

- `src/queries.py` holds the discovery queries and **self-asserts at import time** that
  no make, model, or fuel-type term appears in any of them.
- `tests/test_lexicon.py` asserts the same thing independently.
- Vehicle make is identified from article body text with headlines stripped, so the
  headline never influences which vehicle is treated as the index vehicle.
- The incidents that prompted the hypothesis are recorded in `docs/SEED_EXAMPLES.md`,
  used to check the pipeline finds them — and then excluded from the analysis.
- Crashes discovered but covered by Australian outlets only because of a participant's
  celebrity status (domestic or overseas) are excluded on the same logic: that coverage
  exists via a different editorial mechanism than the one this study measures.

## Layout

```
PROTOCOL.md              study design, pre-registration content
CODEBOOK.md              variable definitions and coding rules, incl. index-vehicle rules
docs/OUTLETS.md          outlet list, ranked by readership, with coverage-gap notes
docs/SEED_EXAMPLES.md    motivating cases (excluded from analysis)
db/schema.sql            SQLite schema for the study database

src/queries.py           frozen brand-agnostic discovery queries
src/lexicon.py           frozen make/model lexicon — produces the primary outcome
src/sitemap_harvest.py   direct-outlet sitemap harvest (primary discovery source)
src/wayback_harvest.py   Wayback Machine harvest (news.com.au)
src/classify_vehicle.py  title-only relevance filter: is this a road-vehicle crash?
src/cluster_incidents.py articles -> candidate incidents
src/promote_incidents.py candidate incidents -> draft `incident` rows, fetches article text
src/llm_coding.py        headline-blinded incident coding (make disambiguation only)
src/apply_adjudication.py applies human adjudication decisions from tools/adjudicate.html
src/merge_incidents.py   fixes one real crash wrongly split across multiple incident rows
src/split_incident.py    fixes unrelated crashes wrongly merged into one incident row
src/apply_cluster_review.py applies per-article "doesn't belong" flags from tools/review_clusters.html
src/build_dataset.py     outcome coding, syndication detection, provenance
src/validate_coding.py   gold-standard check incl. the Tesla-vs-rest recall differential
src/primary.py           THE STUDY. Two conditional probabilities, permutation test. stdlib only
src/analysis.py          appendix — GEE, adjustment, self-matched comparison
src/sensitivity_out_of_control.py  is the effect just a "dramatic crash" effect? (write-up §3.5)
src/export_appendix.py   writes the public data appendix
src/power.py             sample size and detectable-effect calculations
src/simulate.py          synthetic data, so the analysis can be written before the data
tools/                   HTML review interfaces (adjudication, gold-standard coding, cluster review)
templates/               coding sheets for human coders
tests/                   the outcome definition, as executable assertions
```

## Reproducing the result

```bash
pip install -r requirements.txt
python -m pytest tests -q                     # the outcome definition holds
python -m src.power                           # sample size + detectable effect

# Real harvest requires ANTHROPIC_API_KEY for the make-disambiguation step and a machine
# outside the Claude Code sandbox (some harvest sources are blocked by its egress policy).
# The harvest is resumable — re-running the same command skips completed windows.
python -m src.sitemap_harvest --domain smh.com.au --start 2025-09-01 --end 2026-08-31 --db data/study.db
python -m src.cluster_incidents --db data/study.db --out output/candidate_incidents.csv
python -m src.promote_incidents --db data/study.db --csv output/candidate_incidents.csv
python -m src.primary --db data/study.db --start 2025-09-01 --end 2026-08-31
```

`data/study.db` itself is not committed (article body text is never redistributed, per
the scraping conventions below) — reproducing the result from scratch means re-running
the harvest, which takes real wall-clock time across several outlets.

## LLM-assisted coding, and the trap in it

Claude disambiguates vehicle make from article body text only when mechanical lexicon
matching finds two or more candidate makes (`src/llm_coding.py`). Two safeguards: the
model sees body text with **headlines stripped**, and it never codes the outcome (headline
naming) — that comes mechanically from `src/lexicon.py` applied to the headline alone.

The safeguard that matters most is in `src/validate_coding.py`. Overall coding accuracy is
not sufficient:

> If Claude recovers the make from article text more reliably for Teslas than for other
> makes, Tesla incidents get better exposure ascertainment. That is differential
> misclassification pointing the same way as the hypothesis — enough to manufacture the
> entire effect from nothing but the coder.

So validation reports a per-make recall table against an independently hand-coded
gold-standard sample, with an explicit **Tesla-vs-rest recall differential**, hard-capped
at ±0.10. Result: Tesla recall 100% (3/3), non-Tesla recall 92% (12/13), differential
+0.08 — passes, though the underlying sample (28 incidents) is small.

## What this study can and cannot say

It measures **editorial behaviour** — whether a headline names a make. It says nothing
about whether any vehicle is more or less safe.

It also may not end up being only about Tesla. The write-up's robustness checks show a
real, independent luxury-brand naming effect (premium makes named ~22× as often as
mainstream ones) — Tesla still exceeds even that baseline by a further ~4×, but "does
this generalise to other distinctive or expensive cars" is a live, more interesting
question this dataset can gesture at but not settle with n=3.

## Provenance

This project began inside the [coronial](https://github.com/changyang1230/coronial)
repository (an Australian coroners findings database) and was split out with
`git subtree split`, so parts of the commit history predate this repo. It kept the
scraping conventions from there: honour robots.txt, ≥2-second delays between requests to
any host, never stop on errors — log and continue.

Nothing here reads or writes any coronial database.
