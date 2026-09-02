# Does the headline name the car? — study dataset

Generated 2026-09-01T08:56:01+00:00  
Incidents covered by ≥2 of the top 10 Australian news brands: **66** (3 Tesla, 63 non-Tesla), **196** articles.

## The answer

| | articles | headline names the make | **probability** | 95% CI |
|---|---|---|---|---|
| **Tesla** | 7 | 4 | **57.1%** | 25.0% – 84.2% |
| **Not Tesla** | 189 | 7 | **3.7%** | 1.8% – 7.4% |

**Difference: 53.4%** (95% CI 21.1% – 80.5%)  
**Ratio: 15.43×** — a Tesla's make is 15.4 times as likely to appear in the headline.

**p = 0.0014** (permutation test, Tesla label shuffled across incidents — 20,000 permutations)

<sub>Fisher exact on the raw 2×2 gives p = 1.77e-04, but that treats eight articles about one crash as eight independent facts. They are not — outlets copy each other, and whether the make is 'the story' is settled at the incident level. The permutation p above keeps each incident's articles together and is the one to quote.</sub>

## Same question, incident as the unit

| | incidents | median share of covering outlets naming the make | mean |
|---|---|---|---|
| **Tesla** | 3 | **50.0%** | 61.1% |
| **Not Tesla** | 63 | **0.0%** | 3.5% |

Named by at least half the covering outlets: **2/3** Tesla incidents vs **2/63** non-Tesla.

## By make

| Make | incidents | articles | headline names the make |
|---|---|---|---|
| Toyota | 19 | 55 | 0.0% |
| BMW | 4 | 18 | 5.6% |
| Mazda | 4 | 10 | 0.0% |
| Holden | 4 | 9 | 0.0% |
| Ford | 4 | 9 | 0.0% |
| Nissan | 4 | 9 | 11.1% |
| Kia | 3 | 10 | 0.0% |
| Honda | 3 | 9 | 0.0% |
| Tesla | 3 | 7 | 57.1% |
| Audi | 2 | 12 | 16.7% |
| Skoda | 2 | 8 | 0.0% |
| Subaru | 2 | 7 | 0.0% |
| Mercedes-Benz | 2 | 4 | 0.0% |
| Volkswagen | 2 | 4 | 0.0% |
| Isuzu | 1 | 8 | 0.0% |
| Alfa Romeo | 1 | 3 | 0.0% |
| Jaguar | 1 | 3 | 33.3% |
| Mitsubishi | 1 | 2 | 0.0% |
| RAM | 1 | 3 | 0.0% |
| Hyundai | 1 | 2 | 0.0% |
| Ferrari | 1 | 2 | 100.0% |
| SsangYong | 1 | 2 | 0.0% |

Read this table before believing the headline number. If a premium make sits right next to Tesla, the effect may be about distinctive or expensive cars rather than about Tesla specifically — which is a different and more interesting finding.

## What did not make it in

| Reason | incidents dropped |
|---|---|
| make not established | 61 |
| covered by fewer than 2 outlets | 23 |

Candidate incidents: **215**; make could not be determined for **108** (**50%**).
Of the eligible incidents, make established from a media-independent source (police / coronial / court): **0**; from article text only: **0**.

> **This is the denominator to worry about.** For a Tesla, some outlet almost always says so. For a small hatchback, outlets often just write "a car" — and that incident silently leaves the study. The non-Tesla incidents that survive are therefore enriched for ones where *somebody* named the make, which correlates with naming it in the headline. That pushes `p(title | non-Tesla)` **up**, making the gap look **smaller** than it is.
>
> So a positive result survives this bias. A null result does not, and cannot be interpreted without knowing how big that excluded pile was. Run `--tier1-only` to see the version that does not depend on article text at all.

## Sensitivity: coverage threshold

Everything above only includes incidents covered by at least **2** of the top 10 outlets — below that, an incident never enters the probability calculation, the confidence interval, or the permutation test; it only shows up as a count in "What did not make it in" above. That is an unexamined exclusion: if Tesla incidents clear the coverage bar more easily than non-Tesla incidents (plausible, since novelty is what got them covered at all — see the Severity decision in CLAUDE.md), the excluded pile is not a random sample and the threshold itself could be shaping the result. This reruns the same comparison at other thresholds, on the same underlying incident set, to check whether the effect's direction and rough size survive.

| min outlets | incidents (Tesla / non-Tesla) | p(title \| Tesla) | p(title \| non-Tesla) | difference | permutation p |
|---|---|---|---|---|---|
| 1 | 3 / 86 | 57.1% | 3.7% | 53.5% | 0.0019 |
| 2 | 3 / 63 | 57.1% | 3.7% | 53.4% | 0.0014 ⟵ reported above |
| 3 | 1 / 19 | 33.3% | 4.5% | 28.8% | 0.1009 |
| 5 | 0 / 2 | — | — | — | one arm empty |

---

### Reading this

- These are probabilities about **headline writing**, not about vehicle safety. Nothing here says any car is more or less dangerous.
- Quote the permutation p, not the Fisher p.
- Check the by-make table before concluding this is about Tesla.
- `analysis.py` (appendix) adjusts for severity, incident type, vehicle age, jurisdiction and outlet, and runs the self-matched comparison within crashes involving a Tesla *and* another car. Worth running if the gap above is real; pointless if it is not.