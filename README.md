# The Tesla Headline Study

> Are Australian news headlines more likely to name the vehicle's make when the vehicle
> is a Tesla?

A research project testing an intuition: that media reports name "Tesla" in the headline
of vehicle-incident stories more readily than they name other makes. The intuition comes
from memorable examples, which is exactly what a salience effect would produce — so the
impression cannot be evidence for itself. This project is the design that can tell the
two apart.

**Status: protocol written, no data collected.** Nothing here has been run against real
articles yet. **Start with [`docs/PHASE0_RUNBOOK.md`](docs/PHASE0_RUNBOOK.md)** — it
answers whether the study is viable at all before any effort is committed.

**Track: lean** — personal research, done properly. The design integrity stays (brand-blind
frame, freeze before extraction, pre-specified analysis); the journal machinery does not.
Protocol §0 states exactly which is which.

| Document | What it is |
|---|---|
| [`PROTOCOL.md`](PROTOCOL.md) | The study design. Read this first. |
| [`CODEBOOK.md`](CODEBOOK.md) | Every variable definition and coding rule. |
| [`docs/OUTLETS.md`](docs/OUTLETS.md) | The frozen outlet list. |
| [`docs/PHASE0_RUNBOOK.md`](docs/PHASE0_RUNBOOK.md) | Step-by-step feasibility probe with the go/no-go rules. **Run this first.** |
| [`docs/SEED_EXAMPLES.md`](docs/SEED_EXAMPLES.md) | The motivating cases — excluded from the analysis, and why. |

## The design in one paragraph

Harvest five years of Australian vehicle-incident coverage using a query set that
**contains no brand names**. Cluster the articles into incidents. Establish each
incident's vehicle make from police and coronial sources wherever possible. Then, for
every article, ask one mechanical question: does the headline identify the make? Compare
Tesla incidents with everything else using a logistic GEE clustered on incident, and —
the strongest comparison available — compare Tesla against the *other car in the same
crash*, where severity, location, date, outlet and journalist are all held constant
because both makes are competing for the same headline.

## The one thing that could sink this study

If incidents are discovered by searching for crashes, Tesla crashes surface more readily
*because the brand is in the headline*. The exposed and unexposed groups would then be
selected by the outcome, and any result would be circular.

Everything about the sampling frame exists to prevent that:

- `src/queries.py` holds the discovery queries and **self-asserts at import time** that
  no make, model, or fuel-type term appears in any of them.
- `tests/test_lexicon.py` asserts the same thing independently.
- Vehicle makes are ascertained from police and coronial sources (Tier 1) where
  possible, with a pre-specified sensitivity analysis restricted to Tier 1 alone.
- The incidents that prompted the hypothesis are recorded, used to check the pipeline
  finds them — and then excluded from the analysis.

## Layout

```
PROTOCOL.md              study design, pre-registration content
CODEBOOK.md              variable definitions and coding rules
docs/OUTLETS.md          frozen outlet list with ownership groups
docs/SEED_EXAMPLES.md    motivating cases (excluded from analysis)
db/schema.sql            SQLite schema for the study database
src/lexicon.py           frozen make/model lexicon — produces the primary outcome
src/queries.py           frozen brand-agnostic discovery queries
src/gdelt_harvest.py     brand-agnostic article harvest
src/cluster_incidents.py article -> candidate incident clustering
src/build_dataset.py     outcome coding, syndication detection, provenance
src/analysis.py          the pre-specified analysis — run ONCE after dataset lock
src/simulate.py          synthetic data, so the analysis can be written before the data
src/power.py             sample size and detectable-effect calculations
templates/               coding sheets for human coders
tests/                   the outcome definition, as executable assertions
```

## Getting started

```bash
pip install -r requirements.txt

# 1. What sample size does this need, and what could it detect?
python -m src.power

# 2. Check the analysis behaves on data whose answer is known
python -m pytest tests -q
python -m src.simulate --out data/simulated.csv --tesla-or 4.0
python -m src.analysis --csv data/simulated.csv --out output/results_simulated.md

# 3. Phase 0 feasibility — see docs/PHASE0_RUNBOOK.md for the full procedure
python -m src.gdelt_harvest --start 2024-01-01 --end 2024-06-30 --db data/study.db
python -m src.cluster_incidents --db data/study.db --out output/candidate_incidents.csv
```

Step 3 makes live requests and must run on your own machine — `api.gdeltproject.org` is
blocked by the Claude Code web sandbox's egress policy. The harvest is **resumable**: if
it dies, re-run the identical command and it skips completed windows. A full five-year
harvest is ~7,300 API calls at a 2-second delay — roughly four hours, once, overnight.

## Phases

| Phase | Gate |
|---|---|
| 0. Feasibility | Are there ≥25 eligible Tesla incidents? If not, invoke a Protocol §10.4 fallback **now**, not after the analysis. |
| 1. Frame build | Manual incident verification. |
| 2. Freeze | Freeze protocol, lexicon, queries; hashes into `provenance`. Tag `protocol-v1`. |
| 2b. Coder validation | Hand-code 25–30 incidents blind; `validate_coding.py` must pass — including the differential check. |
| 3. Extraction | Headline capture, automated outcome coding, LLM-assisted incident coding + adjudication. Tag `dataset-lock-v1`. |
| 4. Analysis | `python -m src.analysis --db data/study.db`. Run once. |
| 5. Write-up | STROBE-structured manuscript. |

Phase 2 must precede Phase 3. Registering after seeing the outcome data turns a
confirmatory study into an exploratory one wearing a confirmatory costume.

## LLM-assisted coding, and the trap in it

Claude extracts incident-level variables from article body text (`src/llm_coding.py`).
Three safeguards: the model sees body text with **headlines stripped**, it **never codes
the outcome** (that comes from the frozen lexicon), and every value carries an evidence
quote and confidence, with hedges routed to human review.

The safeguard that matters most is in `src/validate_coding.py`. Overall coding accuracy is
not sufficient:

> If Claude recovers the make from article text more reliably for Teslas than for Mazdas,
> Tesla incidents enter the study with better exposure ascertainment. That is differential
> misclassification pointing the same way as the hypothesis — enough to manufacture the
> entire effect from nothing but the coder.

So validation reports a per-make recall table with an explicit **Tesla-vs-rest
differential**, hard-capped at ±0.10, and exits non-zero if it fails. Read that number,
not the headline kappa.

## What this study can and cannot say

It measures **editorial behaviour** — whether a headline names a make. It says nothing
about whether any vehicle is more or less safe, and the manuscript must say so in the
title, not just the discussion.

It also may not end up being about Tesla. If the `Tesla vs premium ICE` contrast comes
out null, the honest conclusion is that distinctive and expensive cars get named and
Tesla is one of them — a different, and more interesting, finding.

## Provenance

This project began inside the [coronial](https://github.com/changyang1230/coronial)
repository (an Australian coroners findings database) and was split out with
`git subtree split`, so the commit history predates this repo. It kept two things from
there: the scraping conventions (honour robots.txt, 2-second delays between requests,
never stop on errors — log and continue), and coroners court findings as a **Tier 1
source for vehicle makes** (Protocol §7.2). Coronial findings are media-independent and
often name the vehicle, which makes them exactly the kind of source this study needs to
break the circularity described above. They lag the incident by years, so they supplement
police media releases rather than replacing them.

Nothing here reads or writes any coronial database.
