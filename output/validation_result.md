# LLM coding validation

Gold-standard incidents: **28**; machine-coded: **374**; overlapping (used): **28**

## Per-variable agreement

| Variable | n | exact agreement | kappa | threshold | verdict |
|---|---|---|---|---|---|
| state | 9 | 0.00 | 0.00 | 0.70 | **FAIL** |
| incident_type | 9 | 0.00 | 0.00 | 0.70 | **FAIL** |
| index_make | 17 | 0.88 | 0.86 | 0.90 | **FAIL** |
| second_make | 4 | 0.00 | 0.00 | 0.70 | **FAIL** |
| victim_child | 8 | 0.00 | 0.00 | 0.70 | **FAIL** |
| multi_vehicle | 9 | 0.00 | 0.00 | 0.70 | **FAIL** |
| fire_involved | 8 | 0.00 | 0.00 | 0.70 | **FAIL** |
| adas_alleged | 6 | 0.00 | 0.00 | 0.70 | **FAIL** |
| driver_notable | 5 | 0.00 | 0.00 | 0.70 | **FAIL** |
| deaths | 9 | 0.00 | — | 0.85 | **FAIL** |
| serious_injuries | 9 | 0.00 | — | 0.85 | **FAIL** |

## Make ascertainment by make — the differential check

| Make | gold incidents | make recovered | recall |
|---|---|---|---|
| Toyota | 4 | 4 | 1.00 |
| Tesla | 3 | 3 | 1.00 |
| Holden | 2 | 2 | 1.00 |
| Mazda | 2 | 2 | 1.00 |
| Ferrari | 1 | 1 | 1.00 |
| Alfa Romeo | 1 | 0 | 0.00 |
| Mitsubishi | 1 | 1 | 1.00 |
| Ford | 1 | 1 | 1.00 |
| Kia | 1 | 1 | 1.00 |

**Tesla recall 1.00 (n=3) vs non-Tesla recall 0.92 (n=13); differential +0.08** — within the +0.10 limit.

## Verdict

**FAIL** — machine coding is not yet admissible for the failing variables. Revise the extraction prompt or hand-code those variables.