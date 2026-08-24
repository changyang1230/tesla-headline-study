# Does the headline name the car? — simulated data

Generated 2026-08-24T11:59:58+00:00  
Incidents covered by ≥5 of the top 10 Australian news brands: **139** (25 Tesla, 114 non-Tesla), **1180** articles.

## The answer

| | articles | headline names the make | **probability** | 95% CI |
|---|---|---|---|---|
| **Tesla** | 222 | 100 | **45.0%** | 38.6% – 51.6% |
| **Not Tesla** | 958 | 265 | **27.7%** | 24.9% – 30.6% |

**Difference: 17.4%** (95% CI 10.3% – 24.5%)  
**Ratio: 1.63×** — a Tesla's make is 1.6 times as likely to appear in the headline.

**p = 0.0091** (permutation test, Tesla label shuffled across incidents — 20,000 permutations)

<sub>Fisher exact on the raw 2×2 gives p = 1.11e-06, but that treats eight articles about one crash as eight independent facts. They are not — outlets copy each other, and whether the make is 'the story' is settled at the incident level. The permutation p above keeps each incident's articles together and is the one to quote.</sub>

## Same question, incident as the unit

| | incidents | median share of covering outlets naming the make | mean |
|---|---|---|---|
| **Tesla** | 25 | **50.0%** | 47.1% |
| **Not Tesla** | 114 | **17.7%** | 27.2% |

Named by at least half the covering outlets: **13/25** Tesla incidents vs **29/114** non-Tesla.

## By make

| Make | incidents | articles | headline names the make |
|---|---|---|---|
| Tesla | 25 | 222 | 45.0% |
| Kia | 15 | 138 | 22.5% |
| Holden | 12 | 98 | 25.5% |
| Mazda | 10 | 85 | 37.6% |
| Mercedes-Benz | 10 | 80 | 33.8% |
| Mitsubishi | 10 | 93 | 21.5% |
| Land Rover | 9 | 69 | 42.0% |
| Toyota | 8 | 61 | 27.9% |
| Nissan | 7 | 52 | 23.1% |
| Audi | 7 | 56 | 42.9% |
| Polestar | 6 | 44 | 22.7% |
| Hyundai | 6 | 57 | 24.6% |
| BMW | 5 | 49 | 20.4% |
| BYD | 5 | 43 | 25.6% |
| Ford | 4 | 33 | 9.1% |

Read this table before believing the headline number. If a premium make sits right next to Tesla, the effect may be about distinctive or expensive cars rather than about Tesla specifically — which is a different and more interesting finding.

## What did not make it in

| Reason | incidents dropped |
|---|---|
| covered by fewer than 5 outlets | 19 |

---

### Reading this

- These are probabilities about **headline writing**, not about vehicle safety. Nothing here says any car is more or less dangerous.
- Quote the permutation p, not the Fisher p.
- Check the by-make table before concluding this is about Tesla.
- `analysis.py` (appendix) adjusts for severity, incident type, vehicle age, jurisdiction and outlet, and runs the self-matched comparison within crashes involving a Tesla *and* another car. Worth running if the gap above is real; pointless if it is not.