# Coding manual

Companion to `PROTOCOL.md`. Every variable in the analysis dataset is defined here.
Coders read this in full before their first case. Where a rule is ambiguous, the coder
records the case in `output/coding_queries.md` rather than guessing; queries are resolved
by the lead investigator and the resolution is added to this file as a numbered rule.

**This file is frozen at Phase 2 registration.** After that, changes are made by adding
dated rules at the bottom of each section, never by editing existing rules.

---

## 1. Incident-level coding

Coded once per incident, from all available sources.

| Variable | Type | Definition |
|---|---|---|
| `incident_id` | text | `YYYYMMDD-STATE-nn`, e.g. `20231105-VIC-01` |
| `incident_date` | date | Date the incident occurred (not reported). Local time. |
| `state` | enum | NSW / VIC / QLD / WA / SA / TAS / NT / ACT |
| `locality` | text | Suburb or town as given by police/first report |
| `remoteness` | enum | metro / regional / remote — by ABS Remoteness Area of `locality` |
| `deaths` | int | Persons who died at scene or within 30 days, all parties |
| `serious_injuries` | int | Persons reported admitted in critical/serious condition |
| `victim_child` | bool | Any deceased or seriously injured person under 18 |
| `incident_type` | enum | See §1.1 |
| `multi_vehicle` | bool | ≥2 motor vehicles involved in the collision |
| `fire_involved` | bool | Any vehicle caught fire |
| `index_make` | text | Make of the index vehicle (§1.2) |
| `index_model` | text | Model where stated, else blank |
| `index_vehicle_year` | int | Build/compliance year where stated, else blank |
| `index_is_bev` | bool | Index vehicle is battery-electric |
| `second_make` | text | Make of the other vehicle in a 2-vehicle incident (§1.3) |
| `make_tier` | enum | `1` media-independent, `2` media-dependent (Protocol §7.2) |
| `make_source` | text | Citation for the make: URL, police release ID, or coronial reference |
| `adas_alleged` | bool | Autopilot, FSD, self-driving, lane-keeping or similar raised in any coverage |
| `driver_notable` | bool | Driver is a public figure independently of this incident |
| `eligible` | bool | Meets all Protocol §6.4 criteria |
| `exclusion_reason` | text | Required when `eligible = false` |

### 1.1 `incident_type`
Assign the **first** matching category, in this order:

1. `pedestrian_cyclist_struck` — a pedestrian, cyclist, or scooter rider was struck.
2. `single_vehicle_fire` — the primary event is a vehicle fire with no collision, or a
   fire that caused the casualties.
3. `occupant_fatal_collision` — a collision in which a vehicle occupant died.
4. `occupant_serious_collision` — a collision with serious injury but no death.
5. `other` — anything else eligible. Requires a free-text note.

Rule: a collision followed by fire in which death was caused by impact is
`occupant_fatal_collision` with `fire_involved = true`, **not** `single_vehicle_fire`.

### 1.2 Index vehicle
The index vehicle is the one whose movement or condition constitutes the event. Apply in
order and stop at the first that resolves:

1. **Single-vehicle incident** — that vehicle.
2. **Pedestrian/cyclist struck** — the vehicle that struck them.
3. **Vehicle fire** — the vehicle that caught fire.
4. **Multi-vehicle collision where one vehicle crossed to the wrong side, ran a signal,
   or otherwise initiated** — the initiating vehicle, as described by police. If police
   have not attributed initiation, go to 5.
5. **Multi-vehicle, no attribution** — the vehicle whose occupants were killed or most
   seriously injured.
6. **Still unresolved** — code `index_make` as `AMBIGUOUS`, set `eligible = false`,
   and record in coding queries. Do not guess.

**The index vehicle is determined from Tier 1 sources wherever they exist, by a reviewer
who has not read the headlines.** This is the single most important procedural safeguard
in the study: if headlines drive the exposure assignment, the study measures nothing.

### 1.3 `second_make`
Populated only for `multi_vehicle = true` incidents with exactly two identified vehicles.
Feeds the within-incident matched analysis (Protocol §9.3). For ≥3 vehicles, record all
makes in `all_makes` (pipe-separated) and exclude from the matched analysis.

### 1.4 Make normalisation
- `Mercedes`, `Merc`, `Mercedes Benz` → `Mercedes-Benz`
- `Range Rover`, `Landrover` → `Land Rover`
- `VW`, `Volkswagon` → `Volkswagen`
- `Holden Commodore` → make `Holden`, model `Commodore`
- Rebadged vehicles are coded to the **badge on the car**, not the manufacturer
  (an MG4 is `MG`, not `SAIC`).
- Model variants collapse to the base model: `Model 3 Performance` → `Model 3`.

---

## 2. Article-level coding

| Variable | Type | Definition |
|---|---|---|
| `article_id` | text | SHA1 of the canonical URL, first 12 chars |
| `incident_id` | text | FK to incident |
| `outlet` | text | Canonical outlet name (`docs/OUTLETS.md`) |
| `outlet_group` | enum | Ownership group |
| `outlet_register` | enum | tabloid / broadsheet / broadcast / public |
| `url` | text | Canonical URL |
| `publish_datetime` | datetime | Earliest known publication timestamp, UTC |
| `headline` | text | Earliest retrievable headline (§2.1) |
| `headline_source` | enum | `wayback` / `gdelt` / `ccnews` / `live` |
| `headline_captured_at` | datetime | Timestamp of the snapshot the headline came from |
| `standfirst` | text | Sub-headline / kicker, if any |
| `is_wire` | bool | AAP byline/credit, or near-duplicate of a wire item |
| `syndication_group_id` | text | Shared by near-duplicate articles |
| `article_wordcount` | int | Body word count |
| `substantive` | bool | See A4 |
| `headline_names_make` | bool | **Primary outcome** — automated (§3) |
| `headline_names_make_strict` | bool | Make token only, no model tokens (sensitivity) |
| `headline_names_second_make` | bool | For the matched analysis |
| `body_names_make` | bool | Negative control outcome |
| `first_mention_position` | enum | headline / standfirst / first_paragraph / later_body / absent |

### 2.1 Headline capture rules
- The headline is the `<h1>` / `og:title` as published, **excluding** the site name
  suffix (`" | news.com.au"`, `" - ABC News"`).
- Strip leading section kickers separated by a colon **only** where the kicker is a
  section label (`Breaking:`, `Live:`, `Exclusive:`). A colon carrying content
  (`Daylesford: five dead`) is part of the headline.
- Where a live-blog entry is the only coverage, use the blog post title, not the blog
  title. If the blog has no per-post title, `substantive = false`.
- Preference order: earliest Wayback snapshot within 14 days of `publish_datetime` →
  GDELT/CC-NEWS title at first crawl → live headline. Record which in `headline_source`.

### 2.2 Article inclusion rules
- **A1** Published within the incident date + 14 days window.
- **A2** Outlet appears on the outlet list.
- **A3** English language.
- **A4 (substantive)** The article's principal subject is the index incident. A
  round-up ("Five things you missed today") or an article about something else that
  mentions the incident in passing is `substantive = false` and is excluded from the
  primary analysis. Operational test: the incident occupies ≥ 50% of the body, or the
  headline refers to it.
- **A5** Opinion columns, editorials and letters are excluded — their headline
  conventions differ. Recorded with `exclusion_reason = opinion`.
- **A6** Duplicate URLs (same canonical URL, different tracking parameters) are merged.

---

## 3. Automated outcome coding — matching rules

The primary outcome is produced by `src/lexicon.py`. These rules define its behaviour and
are testable assertions, not prose; `tests/test_lexicon.py` asserts each one.

### 3.1 Matching
- Case-insensitive, Unicode-normalised (NFKD), curly quotes and en-dashes normalised.
- Whole-token matching with word boundaries. `Teslas` matches (plural suffix allowed);
  `Teslarati` does not.
- Multi-word model tokens (`Model 3`, `Land Cruiser`) match across a single space or
  hyphen.
- Possessives (`Tesla's`) match.

### 3.2 Model tokens count as make identification
A headline identifies the make if it contains the make token **or** a model token
uniquely mapped to that make in the lexicon. Rationale in Protocol §7.3.

Model tokens are included **only** where the mapping is unambiguous to an Australian
reader. Tokens excluded from the lexicon for ambiguity: `Focus`, `Escape`, `Territory`,
`Fit`, `City`, `Civic` (adjective), `Insight`, `Odyssey`, `Colorado`, `Everest`,
`Captiva`, `Cruze`, `Astra`, `Jazz`, `Spark`, `Kona` — each is a common word or place
name in ordinary headline usage.

### 3.3 Tesla-specific disambiguation
`Tesla` is a surname, a unit of magnetic flux density, and a company name. A headline
match is **rejected** if:
- it is followed by `coil`, `Inc`, `Motors` in a non-vehicular sentence, or preceded by
  `Nikola`;
- the headline is about the company (share price, recall, Musk, factory) rather than the
  incident — but note that a *recall* headline is not in the frame anyway, because the
  frame is built from incident coverage.

The same class of rule applies to `Ranger` (`Park Ranger`, `Power Rangers`), `Kia`
(`Kia Ora`), `Polestar` (`pole star`), and `MG` (`mg` dosage — relevant in Australian
health copy). All rejection rules are unit-tested with the real false-positive strings
found during Phase 0.

### 3.4 Human verification of the automated outcome
A 15% random sample of articles is checked by a human against the automated
`headline_names_make`. Disagreement > 2% triggers lexicon revision **before** Phase 4,
and the revision is re-run over the whole dataset. Because the outcome is mechanical,
this is a check on the lexicon, not on coder judgment.

---

## 4. Reliability

| Variable | Method | Threshold |
|---|---|---|
| `index_make` | Dual coding, 20% sample | κ ≥ 0.8 |
| `incident_type` | Dual coding, 20% sample | κ ≥ 0.7 |
| `adas_alleged` | Dual coding, 20% sample | κ ≥ 0.7 |
| `first_mention_position` | Dual coding, 20% sample | weighted κ ≥ 0.7 |
| `substantive` | Dual coding, 20% sample | κ ≥ 0.7 |
| `headline_names_make` | Automated; 15% human check | agreement ≥ 98% |

Below threshold → revise this codebook, retrain, recode that variable in full. Record
every reliability run in `output/reliability.md` including the failed ones.

---

## 5. Rule log

Additions after freeze go here, dated, numbered, with the query that prompted them.

| # | Date | Rule | Prompted by |
|---|---|---|---|
| — | — | *(none yet)* | — |
