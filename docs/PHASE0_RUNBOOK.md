# Phase 0 runbook — feasibility

Run this on your own machine. It answers one question:

> **Are there enough eligible Tesla incidents in Australia for this study to detect
> anything?**

Everything else in the project is wasted effort if the answer is no, so this comes first
and the decision rules are written down *before* the numbers arrive.

Budget: ~30 minutes of setup, ~25 minutes of API calls for the probe, plus an hour of
your attention on the review CSV.

> **Note:** this cannot be run from a Claude Code web session — `api.gdeltproject.org`
> is blocked by the sandbox's egress policy. It runs fine from your own machine.

---

## Setup

From the repository root:

```bash
# venv at the repo root — VS Code auto-detects `.venv` there and `.venv/` is gitignored
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# sanity check before spending any API calls
python -m pytest tests -q     # expect 63 passed
python -m src.power           # read the "detectable" table
```

Every command in this runbook runs from the repository root.

The only credential this project ever needs is `ANTHROPIC_API_KEY`, and not until the
LLM-coding step at the very end. Steps 1–8 need no credentials at all.

## Step 1 — Confirm GDELT is reachable

```bash
python - <<'PY'
import datetime as dt
from src.gdelt_harvest import _fetch, match_outlet
from src.queries import gdelt_queries
arts = _fetch(gdelt_queries()[0], dt.date(2024,3,4), dt.date(2024,3,4))
on = [a for a in arts if match_outlet(a.get("url",""))]
print(f"returned {len(arts)}, on outlet list {len(on)}")
for a in on[:5]:
    print(" -", a.get("domain"), "|", (a.get("title") or "")[:80])
PY
```

**Expect** a handful to a few dozen articles, most from the outlet list.

- Zero returned → the query syntax was rejected. Try `gdelt_queries_narrow()` from
  `src/queries.py` instead and note the substitution.
- Returned but none on the outlet list → check `OUTLET_DOMAINS` against the actual
  domains printed.

## Step 2 — Six-month probe

```bash
python -m src.gdelt_harvest --start 2024-01-01 --end 2024-06-30 --db data/study.db -v
```

~730 calls, ~25 minutes at the 2-second delay. **It is resumable** — if it dies, re-run
the identical command and it skips completed windows.

**Record before moving on:**

```bash
sqlite3 data/study.db "
  SELECT COUNT(*) AS articles, COUNT(DISTINCT domain) AS outlets FROM harvest;
  SELECT domain, COUNT(*) FROM harvest GROUP BY 1 ORDER BY 2 DESC LIMIT 15;
  SELECT COUNT(*) FROM harvest_progress WHERE capped = 1;"
```

⚠️ **If any window is `capped = 1`**, GDELT truncated it at 250 records and coverage is
biased toward quiet news days. Reduce `--window-days` and re-run those windows before
trusting anything downstream.

## Step 3 — Cluster into candidate incidents

```bash
python -m src.cluster_incidents --db data/study.db --out output/candidate_incidents.csv
wc -l output/candidate_incidents.csv
```

## Step 4 — Calibrate the clustering (30 minutes of your time)

Open the CSV. Read `example_headlines` for the first 50 rows and mark each:

- **correct** — one real incident
- **over-merged** — two or more distinct incidents lumped together
- **under-merged** — you can see the same incident split across rows

Then sweep the threshold and pick the value that minimises both:

```bash
for t in 0.25 0.30 0.35 0.40 0.45; do
  echo "threshold $t"
  python -m src.cluster_incidents --db data/study.db --threshold $t \
      --out /tmp/cand_$t.csv 2>&1 | grep "clusters"
done
```

**Record the chosen threshold in `output/phase0_feasibility.md`.** Calibrating here is
safe — the clusterer never sees the outcome — but it must be frozen before Phase 3.

## Step 5 — Count Tesla incidents

Sample 60 candidate clusters at random and determine the make for each from the article
text. This is the number the whole study depends on, so do it by hand — do not let a
model tell you the answer you want.

```bash
shuf -n 60 output/candidate_incidents.csv > /tmp/phase0_sample.csv
```

For each: open two or three of the URLs, record the make, whether it meets the severity
bar (death / critical injury / fire), and how many distinct outlet groups covered it.

## Step 6 — Extrapolate and decide

```
tesla_rate      = tesla incidents / eligible incidents in the sample
eligible_6mo    = eligible clusters in the full 6-month harvest
projected_tesla = tesla_rate x eligible_6mo x 6       # 6 months -> 3 years (2023-2025)
```

The ×6 assumes a flat rate across 2023–2025. That is not exactly true — the fleet kept
growing — but the probe window (H1 2024) sits almost exactly at the **midpoint** of the
study period, so over- and under-estimation roughly cancel. This is the main practical
gain from the three-year window: over 2021–2025 a 2024 probe sat near the end of a period
of steep growth and would have badly overstated the earlier years.

Still report a conservative figure alongside the central one — multiply by 0.8 — and state
both in `phase0_feasibility.md`.

### Decision rules — written before the numbers, honour them

| Projected eligible Tesla incidents | Action |
|---|---|
| **≥ 25** | Proceed to Phase 1 as designed on 2023–2025. |
| **15–24** | Invoke Protocol §10.4 fallback 1 — extend the window back to **2021-01-01** — then recount. This is cheap: the harvest is resumable, so it is `--start 2021-01-01` on the same database and only the new windows are fetched. |
| **8–14** | Fallbacks 1 and 2 (back to 2019-01-01), then 3 (relax severity to any hospitalisation or major property damage). Re-estimate after each. If still under 25, the study is descriptive: report an interval, do not claim a test. |
| **< 8** | Stop, or switch to the within-incident matched design as the *primary* analysis (Protocol §9.3) — it needs far fewer incidents because each article is its own control. Say plainly in the writeup that the between-incident comparison was under-powered. |

Invoke a rung and record it **before** running any outcome comparison. Reaching for a
wider window after seeing a disappointing p-value is a different activity with a
different name.

## Step 7 — Estimate the ICC

The power calculation assumed ρ = 0.5 and the requirement is very sensitive to it. From
30 verified clusters, compute the proportion of articles per incident naming the make and
re-run:

```bash
python -m src.power --rho <observed> --m <observed mean articles per incident>
```

## Step 8 — Write it up

Create `output/phase0_feasibility.md` recording:

- articles harvested, windows capped, outlet coverage
- chosen clustering threshold and its calibration evidence
- clusters found, eligible clusters, mean articles per incident
- observed ICC
- Tesla incidents in the sample, and the projection with its assumptions stated
- **which decision rule fired, and what you are doing about it**

Commit it. This file is the record that the go/no-go call was made on the numbers rather
than on enthusiasm.

---

## The full harvest

```bash
nohup python -m src.gdelt_harvest --start 2023-01-01 --end 2025-12-31 \
      --db data/study.db -v > harvest.log 2>&1 &
tail -f harvest.log
```

~4,400 calls, ~2.5 hours (the H1-2024 probe windows are already done and will be skipped).
Resumable. Do this only **after** Phase 0 says the study is viable — there is no point
harvesting three years to discover there are nine Tesla incidents.

If a §10.4 fallback later widens the window, re-run against the **same database** with the
earlier start date. Completed windows are skipped, so only the new years are fetched:

```bash
python -m src.gdelt_harvest --start 2021-01-01 --end 2025-12-31 --db data/study.db -v
```

## Then: LLM-assisted coding

Once incidents are verified and body text is on disk under `data/bodies/<article_id>.txt`:

```bash
export ANTHROPIC_API_KEY=...            # or: ant auth login
python -m src.llm_coding --db data/study.db --limit 5 --show   # eyeball it first
python -m src.llm_coding --db data/study.db
```

**Then validate before trusting any of it** — hand-code 25–30 incidents yourself
*without reading the machine output first*, mark them `[GOLD]` in `incident.notes`, and:

```bash
python -m src.validate_coding --db data/study.db
```

Read the differential check, not just the headline kappa. If Claude recovers Tesla makes
from article text more reliably than other makes, machine-coded exposure would manufacture
the very effect you are testing for, and the tool says so and exits non-zero.
