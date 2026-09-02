# Tesla Headline Study — session summary, 2025-09-01 to 2026-08-25 window

Written 2026-08-26 to consolidate a long working session into one place. This is a
narrative summary for the researcher, not a replacement for `output/primary_result.md`
(the actual study output) or `PROTOCOL.md`/`CODEBOOK.md` (the frozen design).

---

## 1. Headline result

> **When an Australian outlet covers a car crash and the car is a Tesla, the headline
> names the make 57.1% of the time. When it isn't a Tesla, 2.9% of the time.**
> Difference 54.2 points, ratio 19.4×, permutation p = 0.0004.

Full table and confidence intervals: `output/primary_result.md`.

This is a real, non-trivial finding — but it rests on **3 Tesla incidents**. That number
deserves to be said out loud every time this result is quoted. A 95% CI of 25–84% on the
Tesla side is wide; "57%" is not a precise estimate.

## 2. What the pipeline actually covers

- **Window:** 2025-09-01 to 2026-08-25 (12 months). Older 2023-2025 data exists in
  `data/study.db` but is out of scope and excluded from every query in this pipeline by
  explicit date filter.
- **Sources:** SMH, Nine, Daily Mail, 7NEWS, ABC, SBS (direct sitemap harvest) +
  news.com.au (Wayback + 206 manually-saved sitemap XML files). GDELT is not used.
- **Discovery:** brand-agnostic keyword regex (`src/queries.py` `EVENT_TERMS`), widened
  substantially this session (see §4). 4,849 in-scope candidates in `harvest`.
- **Relevance filter:** `classify_vehicle.py`, LLM (haiku) batch classification of
  titles — is this actually a road-vehicle crash, not aviation/sport/metaphor noise.
- **Clustering/eligibility:** `cluster_incidents.py`, incidents need ≥2 of the top-10
  outlets covering them (see §5 for why 2, not 3).
- **Make coding:** hybrid — mechanical lexicon match first (zero brand-recognition
  differential by construction), LLM (haiku) fallback when 2+ makes are mechanically
  found in headline-stripped body text.
- **Adjudication:** every one of the 212 in-scope incidents has been through human
  review (`tools/adjudicate.html`) — 167 eligible, 45 rejected, 0 undecided.

## 3. Real bugs found and fixed this session (not just data gaps)

- **Duplicate-promotion bug**: cluster labels aren't stable across re-clustering runs;
  fixed dedup to key on article URL instead. (Fixed early, before this window's data.)
- **Partial-overlap promotion gap**: `promote_incidents.py` used to skip an entire
  cluster if *any* URL was already linked to an incident — meaning newly-discovered
  articles for an *existing* incident (e.g. a 3rd outlet catching up on a story) were
  silently never linked. Fixed with `augment_incident()`. This is what let the Ed Husic
  Tesla incident cross the 2-outlet bar.
- **Clustering contamination**: found and fixed two cases of unrelated stories merged
  into one incident (a Bankstown helicopter crash merged into a cyclist-strike incident;
  an unrelated e-bike fatality merged into a car/ute crash). Both caught via the LLM
  coder's own notes flagging "this article describes a different incident."
- **`ascertainment()` denominator bug**: was counting all-time incidents (including
  untouched pre-pivot 2023-2025 rows) as the candidate pool, making "83% make
  undetermined" a meaningless number. Fixed to accept `--start`/`--end`.
- **`export_adjudication.py` re-surfacing rejected incidents**: only checked
  `eligible=1`, so already-rejected incidents would silently reappear for re-review on
  every export. Fixed to check `coded_by='human_adjudication'` instead.
- **`validate_coding.py` undercounting mechanical successes**: only compared against
  `coder='claude'` rows, so mechanically-coded correct answers (most of the dataset)
  were invisible to the Tesla-differential check, producing a false "FAIL" the first
  time it ran. Fixed to include all coders. See §6.

## 4. Scope decisions made this session (all in `CLAUDE.md`, dated)

- **Eligibility threshold: ≥3 outlets → ≥2 outlets.** Made *after* seeing the ≥3 result
  was not significant (p=0.085, 1 Tesla incident) and the ≥2 sensitivity number was
  (p=0.0028 at the time). **This is explicitly NOT a pre-specified decision** — it's
  documented as post-hoc, at the user's informed, explicit request, because this is
  personal research and not for publication.
- **Crash location: domestic Australian crashes only.** Discovery is brand-agnostic but
  not geography-agnostic, so a handful of overseas incidents (Rudy Giuliani/NH, a
  Nigerian expressway crash, an NFL coach's Palo Alto crash, an East Hampton NY crash)
  entered the sample purely because a public figure was involved. Excluded — the
  editorial mechanism (celebrity notability) is different from the one being studied.
- **Professional motorsport excluded** (Bathurst 1000 and Bathurst 6 Hour incidents) —
  naming the make in racing coverage is a genre convention, not an editorial choice.
- **GDELT dropped entirely** — sitemap harvest + Wayback/manual is now the full
  discovery source set.
- **`EVENT_TERMS` widened twice**: first pass added EV-fire and loss-of-control
  vocabulary (thermal runaway, airborne, etc.); second pass added precision-tested
  impact phrases (`car hit`, `hit by`, `bollard`) after empirically checking false-positive
  rates on cached sitemap data before adding anything (`hit`/`street` bare were tested
  and rejected — too noisy; `rammed into` was tested and rejected — collides with the
  RAM brand as a substring).
- **Explicitly refused**: adding brand names (Tesla, Toyota, etc.) to discovery, even
  though it would trivially have caught the "Tesla goes airborne" headline that started
  the vocabulary-widening conversation. This would make discovery success conditional on
  the outcome variable — the one thing the protocol says can invalidate the whole study.

## 5. Known, accepted limitations — say these when you quote the result

- **n=3 Tesla incidents.** The whole effect rests on this. Read the CIs, not just the p-value.
- **50% ascertainment gap** (106 of 212 candidate incidents have no determined make) —
  documented bias direction: this inflates the non-Tesla probability, making the
  Tesla/non-Tesla gap look *smaller* than the true gap, not larger. A positive result
  survives this bias; it would matter more for a null result.
- **Outlet coverage gaps, all documented in `docs/OUTLETS.md`**: Guardian and bbc.com
  never worked (Wayback CDX blocked/times out). Yahoo dropped entirely (unrecoverable,
  ~1.7% Wayback coverage). SBS has a real ~5-month blind spot (2026-04 onward — SBS's own
  sitemap generation lags real time). ABC has a real ~4-week blind spot (2026-07-27
  onward, same lag pattern) — **confirmed via a real miss**: a Tesla-vs-bollard incident
  in Adelaide (2026-08-14) was invisible to both ABC and 7NEWS (video-only coverage
  there) and was only recovered by manually fetching the SMH and Nine.com.au versions
  directly once the headline text was known.
- **The "≥2 outlets" threshold is post-hoc**, not blind — see §4. If this work is ever
  shared beyond personal use, lead with that, not the p-value.
- **The appendix (`analysis.py`, adjusted models) was run and found broken** — every
  adjustment covariate (deaths, multi-vehicle, vehicle age, etc.) is empty in the real
  `incident` table, because the fast adjudication workflow only ever confirmed
  `index_make`/`eligible`, never the rest of the Codebook fields. The "OR 137.76
  adjusted" number in `output/results.md` is not real — don't quote it. The unadjusted
  number there (OR 71.15) just restates the primary result as an odds ratio.
- **Syndication detection**: `build_dataset.py` was run (previously an unrun step) —
  found 9 articles in syndication groups, marked `is_wire`. Available as
  `article.is_wire`/`syndication_group_id` if you want to re-run `primary.py` restricted
  to one-article-per-wire-group as a sensitivity check.

## 6. The gold-standard validation — the check that matters most

Built two hand-coding tools (`tools/gold_code.html`, `tools/resolve_disagreements.html`)
specifically because this check requires an independent human reader, not an LLM — using
me to "validate" myself would defeat the purpose.

**Result (28 incidents hand-coded blind, 6 disagreements manually resolved by rereading
source text): Tesla recall 3/3 = 1.00, non-Tesla recall 12/13 = 0.92, differential +0.08
— within the ±0.10 safety limit.** No evidence the coder is differentially better at
spotting Tesla than other makes. This is the specific failure mode that would have made
the whole result a coding artifact rather than a real finding, and it didn't happen.

Caveat: still a small check (16 known-make comparisons total). "No evidence of bias,"
not "proven unbiased." The one real miss found (Alfa Romeo, mechanical coding found
nothing) was non-Tesla, no pattern.

## 7. What's genuinely still open, if you want to keep going

- The appendix's real adjustment (§5) — would need a second adjudication pass on
  deaths/incident_type/multi_vehicle/etc. for 167 eligible incidents, same scale of work
  as the make adjudication already done.
- A full LLM sweep of the ~240,000 seen-but-discarded URLs to catch more "airborne"-style
  brand-led headlines systematically — explicitly ruled out this session on cost grounds
  (Claude Max rate limits), not on principle.
- `vehicle_age_band`, `remoteness`, `make_tier` are never extracted by the current LLM
  schema at all — `make_tier` is trivially always "2" given no police/coronial source
  exists in this pipeline; the other two would need new extraction prompt work.
- Wayback CDX backfill for the SBS/ABC gaps was attempted and abandoned (repeated
  timeouts, same failure mode as Guardian/bbc.com) — not retried since.

## 8. File index

| File | What it is |
|---|---|
| `output/primary_result.md` | THE result — read this first |
| `output/results.md` | Appendix — unadjusted number only is real, see §5 |
| `output/validation_result.md` | Gold-standard check — differential passes, ignore the other-fields FAILs |
| `output/gold_standard.csv` | The 28-incident hand-coded answer key, fully resolved |
| `docs/OUTLETS.md` | Every outlet coverage gap, with dates and root causes |
| `CLAUDE.md` | All frozen decisions, dated, with the post-hoc ones honestly labelled as such |
