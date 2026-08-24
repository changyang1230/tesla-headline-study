# Results — simulated data

Generated 2026-08-24T08:03:32+00:00  
Articles: **1248** across **158** incidents (**28** Tesla, 130 non-Tesla)

> Pre-specified in PROTOCOL.md section 9. Anything not in `src/analysis.py` at dataset lock is post-hoc and must be labelled as such.

## Table 1 — incidents and coverage by make group

| make_group | incidents | articles | articles/incident | deaths (mean) | child victim % | multi-vehicle % | vehicle <=2y % | metro % | tier 1 make % | HEADLINE NAMES MAKE % | body names make % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mainstream_ice | 77 | 634 | 8.2 | 0.92 | 5.2 | 37.7 | 16.9 | 41.6 | 55.8 | 24.6 | 57.9 |
| other_bev | 17 | 109 | 6.4 | 0.76 | 0.0 | 29.4 | 5.9 | 70.6 | 58.8 | 25.7 | 71.6 |
| premium_ice | 36 | 272 | 7.6 | 0.81 | 8.3 | 38.9 | 16.7 | 58.3 | 47.2 | 33.5 | 74.6 |
| tesla | 28 | 233 | 8.3 | 0.82 | 3.6 | 46.4 | 46.4 | 75.0 | 67.9 | 45.1 | 76.0 |

Estimated intracluster correlation (exchangeable working correlation): **0.332**. The power calculation assumed 0.50; `python -m src.power --rho 0.33` re-derives the requirement.

## Primary analysis — Tesla vs all other makes

Adjusted GEE (exchangeable, clustered on incident, robust SE): **OR 2.12 (95% CI 1.17–3.83), p = 0.0126; cluster-bootstrap CI 1.00–3.79**

Unadjusted: OR 2.46 (95% CI 1.44–4.19), p = 0.0010

Interpretation: the adjusted odds that a headline identifies the vehicle's make are higher for Tesla by a factor of 2.12. This is a statement about **editorial behaviour**, not about vehicle safety.

## Incident-level companion analysis

Median proportion of covering articles naming the make: Tesla **0.52** (n=28) vs other **0.15** (n=130); Mann–Whitney p = 0.0016
Adjusted quasi-binomial GLM: OR 1.88 (95% CI 1.49–2.39), p = 0.0000 (dispersion 0.42)

## Secondary objectives (Holm-adjusted family of three)

| Contrast | OR | 95% CI | p (raw) | p (Holm) |
|---|---|---|---|---|
| Tesla vs other BEV | 2.62 | 1.03–6.63 | 0.0423 | 0.0845 |
| Tesla vs premium ICE | 2.02 | 0.97–4.21 | 0.0594 | 0.0845 |
| Within-incident (matched) | 4.67 | 1.93–11.27 | 0.0002 | 0.0006 |

**Within-incident detail** — 13 multi-vehicle incidents involving a Tesla and one other identified make, 102 articles. Named both: 18; Tesla only: **28**; other make only: **6**; neither: 50. McNemar exact p = 0.0002.

This is the comparison least vulnerable to confounding, because both makes are in the same crash competing for the same headline. If it disagrees with the primary analysis, it is the finding, not a footnote (Protocol section 9.3).

## Negative controls (Protocol section 9.4)

**Outcome control** — make named anywhere in the body: OR 2.05 (95% CI 1.00–4.20), p = 0.0500

A large headline effect with a null body effect points to headline-specific salience. Similar effects on both would instead suggest the Tesla was simply easier to identify, which is a different claim.

**Exposure control** — Toyota vs other non-Tesla makes: OR 0.82 (95% CI 0.21–3.14), p = 0.7710

Toyota is the highest-volume make on Australian roads with no salience narrative attached. A large effect here would mean the model is picking up something other than brand salience.

## Sensitivity analyses

| Analysis | Rationale | OR | 95% CI | p |
|---|---|---|---|---|
| Tier 1 make only | removes media-dependent make ascertainment (§7.2) | 1.59 | 0.71–3.56 | 0.2616 |
| Make token only | excludes model tokens from the outcome (§7.3) | 2.00 | 1.13–3.53 | 0.0166 |
| One article per wire group | removes syndicated duplication (§8.4) | 2.09 | 1.16–3.74 | 0.0137 |
| Excluding wire copy | original reporting only | 2.02 | 1.12–3.66 | 0.0196 |
| Independence working correlation | GEE working-structure robustness | 1.90 | 1.07–3.39 | 0.0288 |
| Unadjusted | no covariate adjustment | 2.46 | 1.44–4.19 | 0.0010 |

## Mediator-adjusted model (Protocol section 9.5 — descriptive only)

Adding the self-driving and fire narratives: OR 1.45 (95% CI 0.69–3.04), p = 0.3228 (primary was OR 2.12).

Reported descriptively. These are mediators, not confounders, so this is *not* a better-adjusted estimate — it shows how much of the association travels with those two narratives. Formal mediation identification assumptions are not met here.

## Subgroups (exploratory, unadjusted for multiplicity)

| Subgroup | n articles | OR | 95% CI | p |
|---|---|---|---|---|
| outlet_register = broadcast | 174 | 2.52 | 1.08–5.89 | 0.0328 |
| outlet_register = broadsheet | 360 | 2.41 | 1.21–4.78 | 0.0119 |
| outlet_register = public | 358 | 2.61 | 1.39–4.91 | 0.0029 |
| outlet_register = tabloid | 356 | 2.24 | 1.09–4.60 | 0.0283 |
| incident_type = occupant_fatal_collision | 573 | 3.01 | 1.39–6.50 | 0.0052 |
| incident_type = occupant_serious_collision | 258 | 3.09 | 1.11–8.57 | 0.0301 |
| incident_type = pedestrian_cyclist_struck | 330 | 2.74 | 1.02–7.39 | 0.0463 |
| remoteness = metro | 677 | 1.99 | 1.05–3.78 | 0.0339 |
| remoteness = regional | 438 | 4.12 | 1.41–12.04 | 0.0097 |

Hypothesis-generating only. No multiplicity control applied, and with this many strata some interval will exclude 1 by chance.

---

### Reading these numbers

- The estimand is a contrast of **editorial behaviour**: whether a headline names the make. It says nothing about whether any vehicle is more or less safe, and the manuscript must say so in the title and abstract.
- The comparison is observational. Makes are not randomly assigned to crashes, and the adjustment set is an assumption (Protocol Appendix A), not a guarantee.
- If the Tier-1-only sensitivity analysis differs materially from the primary estimate, believe the Tier-1 one and say so.
- Report the interval, not the p-value, as the finding.
