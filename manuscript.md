---
layout: page
title: Academic Write-up
permalink: /manuscript.html
---

*[Main article]({{ '/' | relative_url }}) · Academic Write-up · [Appendix]({{ '/appendix.html' | relative_url }})*

# Does the Media Really Say "Tesla" More Often? A Twelve-Month Look at Australian Crash Headlines

*A personal research project — not peer-reviewed, but built the way one should be.*

---

## Abstract

Opinion is split on whether Australian media disproportionately names "Tesla" in
car-crash headlines compared to other car brands. This is a testable claim. Using a
brand-agnostic discovery method across seven major Australian news outlets over a
12-month window (September 2025–August 2026), 196 articles from 66 broadly-reported car
accidents with a determined vehicle make were analysed, of which 7 articles in 3
accidents involved a Tesla. Headlines named the vehicle's make in 57.1% of Tesla-related
articles versus 3.7% of articles about other makes (95% CI 25.0–84.2% and 1.8–7.4%
respectively; permutation test clustered by incident, p = 0.0014; clustered logistic
regression odds ratio 38.86, 95% CI 7.73–195.39). The effect survives several robustness
checks — it is not fully explained by a general "luxury car" naming effect (premium
non-Tesla brands: 15.4%), not an artifact of one tabloid outlet's house style (the gap
persists when this outlet is excluded), and not a "dramatic out-of-control crash" effect
either: restricted to only incidents where a car crashed into a structure or otherwise
went out of control — the same narrative type as most of the Tesla incidents — Tesla is
still named roughly 12× more often than other makes in the same category. It is,
however, built on a small number of Tesla incidents and a population deliberately
restricted to incidents with a determined vehicle make (excluding roughly half of all
candidate incidents where no source ever established what car was involved), and several
further methodological limitations — most importantly the exclusion of video and
social-media coverage — are discussed in detail. The result should be read as suggestive
and well-supported by the available data, not as a definitive, generalizable finding.

---

## 1. Introduction

Among Tesla owners, EV advocates, and casual observers of car-crash news, a specific
claim circulates persistently: that Australian (and international) media are unusually
likely to name "Tesla" explicitly in a crash headline, in a way they would not for a
Toyota or a Ford involved in an identical incident. This claim is contested. One
position holds it as self-evidently true and indicative of editorial bias against the
brand; the opposing position holds it as selective perception aligned with brand allegiance.

Both positions are argued almost entirely from anecdote. This project asks the narrower,
empirically tractable version of the question:

> **When an Australian news outlet covers a car crash, how often does the headline name
> the vehicle's make, and does this probability differ when the vehicle is a Tesla?**

This is explicitly *not* a study of vehicle safety, crash rates, or driver fault. It is a
study of editorial word choice, conditional on a crash having already occurred and
already been covered.

### 1.1 The central methodological problem

The naive approach — searching news archives for "Tesla crash" and "Toyota crash" and
comparing headline counts — is circular. A search conditioned on the brand name
guarantees that every retrieved article already contains that brand name, which
manufactures the very outcome being measured before any data is collected. A more credible
approach should discover candidate incidents through means entirely blind to the vehicle's
make, and only determine the make afterward, from the article content.

---

## 2. Methods

The study window is **September 1, 2025 to August 31, 2026 inclusive** — a full twelve
calendar months. All harvesting, clustering, adjudication, and coding described below
was restricted to crashes occurring, and coverage published, within this window.

### 2.1 Source frame

The source frame was the ten highest-readership Australian online news brands by
[Ipsos iris](https://www.iabaustralia.com.au/) — Australia's official digital audience
measurement currency, endorsed by IAB Australia, which replaced the Nielsen Digital
Panel in mid-2021 and publishes monthly cross-platform (browser and app) audience
rankings of news brands. The ranking used here was averaged across three Ipsos iris
"Top 10 News Category (excluding Weather & Aggregators)" monthly reports (March, May,
and June 2026, `iris-au.ipsos.com`; summary tables also distributed via IAB Australia,
`iabaustralia.com.au`): ABC News, news.com.au, 9News/nine.com.au, The Guardian
Australia, 7NEWS, Sydney Morning Herald, SBS News, Daily Mail Australia, Yahoo News
Australia, and bbc.com.

Of these ten, **seven were practically harvestable**. The Guardian and bbc.com's article
archives proved systematically unreachable for automated collection over the study
window after repeated attempts. Yahoo News Australia's own live index exposes only
approximately one day of current content with no accessible historical archive, making
12 months of retrospective collection infeasible. These three brands are excluded from
the entire dataset, not merely from specific dates.

### 2.2 Discovery: brand-agnostic keyword search

Candidate articles were identified by searching each outlet's own article index (not a
ranked search engine, which introduces its own engagement-driven selection bias) for
generic crash-event vocabulary — terms such as "crash," "collision," "rolled," "T-boned,"
"hit by a car," and "airborne" — with **no brand, model, or fuel-type term permitted in
any discovery query at any point.** This produced 4,898 in-scope candidate articles.

### 2.3 Relevance filtering

Each candidate title was screened by a language-model classifier for whether it plausibly
described a genuine road-vehicle crash, as opposed to unrelated matches on the same
vocabulary (sporting "collisions," financial-market "crashes," aviation incidents,
metaphorical usage). This classification was performed on title text alone, never on
vehicle make, and reduced the candidate set to 2,580 confirmed road-vehicle-crash
articles.

### 2.4 Clustering and eligibility

Articles were clustered into candidate incidents by textual similarity within date
windows, targeting the same **at least two** of the ten source-frame brands threshold used
in the primary comparison, yielding 215 candidate incidents with full article text
retrieved for each. Because a small number of article fetches fail after clustering
(dead links, thin extraction, archive gaps), an incident clustered around two outlets can
end up with only one successfully retrieved article — this is caught and handled at the
analysis stage (§2.7).

### 2.5 Human adjudication

Every one of the 215 candidate incidents was reviewed individually and blind by a human
adjudicator, using a purpose-built review interface, to confirm (a) that the incident was
a genuine, in-scope road-vehicle crash and (b) that the machine-suggested vehicle make was
correct. Adjudication was exhaustive: zero incidents were left undecided. This process
resulted in 150 incidents confirmed as genuine, correctly-coded, in-scope crashes, and 65
exclusions.

**Exclusion categories.** Exclusions were applied on principled, pre-stated grounds
rather than case-by-case judgment:

- *Professional motorsport* (e.g., Bathurst 1000/6 Hour racing incidents) was excluded
  because naming the vehicle in racing commentary is a genre convention, not an editorial
  decision comparable to ordinary crash reporting.
- *International incidents covered only due to a public figure's involvement* (e.g., a
  crash involving a U.S. political figure or a Hollywood actor, reported by Australian
  outlets purely as celebrity news) were excluded because the editorial mechanism
  generating coverage (individual notability) differs from the mechanism under study
  (ordinary domestic crash reporting).
- *Domestic crashes covered primarily due to a participant's public-figure status* — the
  same mechanism as above, minus the geography: a small number of Australian crashes were
  covered because the person involved was a minor celebrity (e.g., a retired professional
  athlete), not because of the crash itself. These were held to a higher bar than
  incidental celebrity mentions — excluded only where the person's notability was
  plainly the reason the story existed at all, not merely a detail within an
  otherwise-ordinary crash report.

A separate, later manual pass specifically re-checked every adjudicated incident's
article-level clustering correctness — not "is this a real incident" but "does every
linked article actually describe the same real-world crash" — which is how the celebrity
exclusions above were caught in full; a handful had passed initial adjudication. This pass
also caught clustering errors in both directions: distinct real-world crashes that had
been merged into one incident because of similar generic phrasing (e.g. two unrelated
"Hume Highway" crashes, ~140km apart, that were never the same event), and coverage of a
single real-world crash that had been split across two or three separate incident rows
because it spanned multiple days (an initial crash report, then a bail hearing, then a
conviction) and fell outside the clustering step's similarity window. Both were corrected
by merging or splitting the affected incident rows and re-verifying make coding against
the corrected article set.

### 2.6 Two further population restrictions before the primary comparison

Of the 150 incidents confirmed as genuine and correctly coded, two further restrictions
are applied before an incident enters the primary comparison — both decided on
construct-validity grounds, not to shape the result.

**A determined vehicle make.** "Does the headline name the make" presupposes a make to
name. For **61 of the 150** incidents, no source — no outlet, no witness quote, no line
of body text anywhere in coverage — ever established what car was involved. These are
not cases where a headline failed to name a *known* brand; there is no ground truth to
check the headline against, so including them would silently answer a different question
("did any brand information survive into coverage at all") instead of the one this study
asks. All 61 are necessarily excluded before either arm of the comparison is formed. This
restriction is discussed further, including its own limitation, in §3.2.

**Outlet coverage.** Of the remaining 89 incidents, 23 ended up with only one
successfully-retrieved article — usually because one of the two originally-clustered
articles could not be fetched (dead link, thin extraction) — and so no longer clear the
≥2-outlet threshold from §2.4. These are excluded from every reported probability,
confidence interval, and p-value on the same coverage-comparability grounds as §2.4
itself.

**66 incidents** (3 Tesla, 63 non-Tesla) satisfy both restrictions and enter the primary
comparison. This distinction matters for transparency: a data appendix or review tool
that lists "150 confirmed incidents" without applying both filters would include
incidents that never actually influence the reported result.

### 2.7 Make identification

Vehicle make was identified from article body text, with headlines and standfirsts
programmatically stripped before this step, to prevent the headline itself from
influencing which vehicle was treated as the index vehicle. Identification used a hybrid
approach: mechanical lexicon matching when body text unambiguously named one vehicle, and
a language-model reader when multiple vehicles were mentioned and disambiguation was
required. All machine suggestions were subject to the human adjudication described above.

### 2.8 Pipeline overview

**Figure 1** summarizes the full pipeline described in §2.2–2.6, with the actual number
of articles/incidents retained (or excluded) at each stage.

<div id="flowchart-embed">
<style>
  #flowchart-embed { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: #ffffff; padding: 32px 16px; border-radius: 8px; margin: 24px 0; }
  #flowchart-embed .wrap { max-width: 720px; margin: 0 auto; }
  #flowchart-embed h1 { font-size: 20px; text-align: center; color: #14161a; margin: 0 0 6px; border: none; }
  #flowchart-embed .subtitle { text-align: center; color: #6b7078; font-size: 13px; margin-bottom: 28px; }
  #flowchart-embed .stage { border: 2px solid #2c3038; border-radius: 12px; padding: 14px 20px; margin-bottom: 4px; background: #f7f8fa; }
  #flowchart-embed .stage.highlight { border-color: #4f8cff; background: #eef4ff; }
  #flowchart-embed .stage .label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: #6b7078; font-weight: 600; margin-bottom: 4px; }
  #flowchart-embed .stage .main { font-size: 15px; color: #14161a; font-weight: 600; }
  #flowchart-embed .stage .detail { font-size: 12.5px; color: #4a4f57; margin-top: 6px; line-height: 1.5; }
  #flowchart-embed .stage .num { color: #4f8cff; font-weight: 700; }
  #flowchart-embed .stage .num.reject { color: #e05252; }
  #flowchart-embed .arrow { text-align: center; color: #9aa0a8; font-size: 20px; margin: 2px 0; }
  #flowchart-embed .split { display: flex; gap: 14px; margin-bottom: 4px; flex-wrap: wrap; }
  #flowchart-embed .split .stage { flex: 1; min-width: 220px; margin-bottom: 0; }
  #flowchart-embed .split .stage.pass { border-color: #34a853; background: #eefaf0; }
  #flowchart-embed .split .stage.fail { border-color: #cccfd4; background: #f5f5f6; }
  #flowchart-embed .split .stage.pass .num { color: #1e8e3e; }
  #flowchart-embed .final { border: 3px solid #4f8cff; border-radius: 14px; padding: 18px 20px; background: #14161a; color: white; text-align: center; margin-top: 4px; }
  #flowchart-embed .final .main { font-size: 17px; font-weight: 700; }
  #flowchart-embed .final .detail { color: #c7cbd1; font-size: 12.5px; margin-top: 8px; }
  #flowchart-embed .final .num { color: #82b1ff; font-weight: 700; }
  #flowchart-embed .footnote { text-align: center; color: #9aa0a8; font-size: 11px; margin-top: 20px; }
</style>
<div class="wrap">
  <h1>How the dataset was built</h1>
  <div class="subtitle">2025-09-01 to 2026-08-31 &middot; 7 Australian news outlets &middot; brand-agnostic discovery</div>

  <div class="stage">
    <div class="label">Step 1 — Discovery</div>
    <div class="main">Generic crash-language search (never a brand name)</div>
    <div class="detail">"crash," "collision," "rolled," "T-boned," "hit by a car," "airborne" &hellip; searched across each outlet's own article index &mdash; not a ranked search engine, which would itself bias toward high-engagement (brand-name) headlines.</div>
    <div class="detail"><span class="num">4,898</span> candidate articles matched, out of the full daily output of 7 outlets</div>
  </div>
  <div class="arrow">&#8595;</div>

  <div class="stage">
    <div class="label">Step 2 — Relevance filter</div>
    <div class="main">AI check: is this actually a road-vehicle crash?</div>
    <div class="detail">Filters out sport "collisions," stock-market "crashes," aviation, metaphor. Decided from the title alone &mdash; never from make or brand.</div>
    <div class="detail"><span class="num">2,580</span> confirmed real road-vehicle crash candidates</div>
  </div>
  <div class="arrow">&#8595;</div>

  <div class="stage">
    <div class="label">Step 3 — Clustering</div>
    <div class="main">Group articles describing the same real-world crash</div>
    <div class="detail">Only crashes covered by <strong>2 or more</strong> of the top 10 Australian news brands are kept &mdash; a single outlet's editorial quirk can't create an incident on its own.</div>
    <div class="detail"><span class="num">215</span> candidate incidents, real article text fetched for every one</div>
  </div>
  <div class="arrow">&#8595;</div>

  <div class="stage highlight">
    <div class="label">Step 4 — Human review</div>
    <div class="main">Every single incident read and adjudicated by hand</div>
    <div class="detail">Blind, one at a time, via a purpose-built review tool &mdash; is this really a road crash, is the AI's suggested make correct? Zero incidents left undecided.</div>
  </div>
  <div class="arrow">&#8595;</div>

  <div class="split">
    <div class="stage pass">
      <div class="label">Kept</div>
      <div class="main"><span class="num">150</span> confirmed real incidents</div>
      <div class="detail">3 Tesla, 147 other makes</div>
    </div>
    <div class="stage fail">
      <div class="label">Excluded</div>
      <div class="main"><span class="num reject">65</span> incidents rejected</div>
      <div class="detail">Overseas crashes, celebrity-driven domestic crashes, professional motorsport, non-crash noise, wrong clustering</div>
    </div>
  </div>
  <div class="arrow">&#8595;</div>

  <div class="stage">
    <div class="label">Step 5 — Determined make required</div>
    <div class="main">Does any source establish what car was involved?</div>
    <div class="detail">"Does the headline name the make" presupposes a make to name &mdash; an incident with no ground truth to check the headline against answers a different question, not this one.</div>
    <div class="detail"><span class="num">89</span> incidents have a determined make &mdash; <span class="num reject">61</span> confirmed-real incidents are excluded because no source ever established what car it was</div>
  </div>
  <div class="arrow">&#8595;</div>

  <div class="stage">
    <div class="label">Step 6 — Coverage threshold (re-checked)</div>
    <div class="main">Does the incident still have ≥2 retrievable outlets?</div>
    <div class="detail">Clustering targeted 2+ outlets, but some article fetches fail after the fact (dead links, thin extraction) &mdash; re-verified here against what was actually retrieved, not just what was originally clustered.</div>
    <div class="detail"><span class="num">66</span> incidents enter the primary comparison &mdash; <span class="num reject">23</span> more are excluded for having only 1 retrievable outlet</div>
  </div>
  <div class="arrow">&#8595;</div>

  <div class="stage">
    <div class="label">Step 7 — Independent accuracy check</div>
    <div class="main">Hand-coded gold standard, blind to the AI's answers</div>
    <div class="detail">28 incidents independently re-read by a human with no AI suggestion visible, specifically to test whether the AI was better at spotting "Tesla" than other brands.</div>
    <div class="detail">Tesla recall <span class="num">100%</span> vs. non-Tesla recall <span class="num">92%</span> &mdash; no bias detected</div>
  </div>
  <div class="arrow">&#8595;</div>

  <div class="final">
    <div class="main">Result: headline names the make</div>
    <div class="detail"><span class="num">57.1%</span> of the time for Tesla &nbsp;vs&nbsp; <span class="num">3.7%</span> of the time for everything else</div>
    <div class="detail">p = 0.0014, permutation test clustered by incident (not by article)</div>
  </div>

  <div class="footnote">Full methodology, caveats, and every incident's sources: see the data appendix.</div>
</div>
</div>

### 2.9 Validation of the make-identification process

A specific validity threat was identified and tested directly: if the language-model
reader were more reliable at recognizing "Tesla" in text than other brands, this alone
could manufacture a spurious Tesla effect independent of any real editorial behavior. A
28-incident gold-standard sample (including all 3 Tesla incidents) was independently
hand-coded by a human reader with no access to the machine's suggested answers, and
compared against the machine's actual output. Result: Tesla recall 100% (3/3) versus
non-Tesla recall 92% (12/13), a differential of +0.08, within a pre-specified ±0.10
tolerance. No evidence of differential recognition bias was found, though the underlying
sample is small.

### 2.10 Statistical analysis

The primary comparison is two conditional probabilities — P(headline names make | Tesla)
versus P(headline names make | not Tesla) — computed over all articles belonging to
incidents that clear both restrictions in §2.6: a determined vehicle make, and coverage
by at least two of the ten source-frame outlets.

Because multiple articles about the same incident are not independent observations
(outlets frequently republish or closely follow each other's coverage of a single event),
significance testing was conducted at the **incident level**, not the article level: the
Tesla/non-Tesla label was permuted across incidents (20,000 permutations), preserving each
incident's internal cluster of articles, and the resulting null distribution used to
compute an honest p-value. For comparison, a naive article-level Fisher's exact test is
also reported to illustrate the magnitude of the non-independence problem.

A clustered logistic regression (Generalized Estimating Equations, exchangeable working
correlation, cluster-robust standard errors, clustering on incident) was additionally fit
on the article-level data, over the identical population, to express the effect as an
odds ratio.

---

## 3. Results

### 3.1 Primary result

| | Incidents | Articles | Headline names make | Rate | 95% CI |
|---|---|---|---|---|---|
| Tesla | 3 | 7 | 4 of 7 | **57.1%** | 25.0% – 84.2% |
| Non-Tesla | 63 | 189 | 7 of 189 | **3.7%** | 1.8% – 7.4% |

Difference: 53.4 percentage points (95% CI 21.1% – 80.5%). Rate ratio: 15.4×.

A naive article-level Fisher's exact test, treating all 196 articles as independent
observations, gives p = 1.77e-04. Because articles clustered within one incident are not
independent, this understates the true uncertainty. The incident-clustered permutation
test gives the appropriate estimate: **p = 0.0014**.

The clustered logistic regression gives an odds ratio of **38.86 (95% CI 7.73–195.39)** for
the Tesla term — a Tesla-involved crash is estimated to be roughly 39 times more likely to
have its make named in the headline than a non-Tesla crash, holding the same clustering
structure that underlies the p-value above. This odds ratio is numerically larger than
the simple 15.4× rate ratio; this divergence is expected and not a contradiction — odds
ratios and rate ratios coincide only when the outcome is rare, and 57.1% is far from rare.

### 3.2 Ascertainment: why a determined make is required, and what that costs

§2.6 already stated the mechanics: 61 of the 150 confirmed incidents (roughly 40%) have
no determined vehicle make and are excluded from the primary comparison entirely, for
both arms. Zoomed out to the full 215-incident candidate pool (including the 65 excluded
for other reasons in §2.5), the same pattern holds even more starkly — no vehicle make
could be established from any source for 108 of 215 candidates (50%). This is a
structural feature of ordinary crash reporting, not a gap specific to this study's
sources: a Tesla's brand is nearly always established by *someone* in coverage, while a
common hatchback's brand is often simply never mentioned at all.

That asymmetry matters for how to read the result, in two ways that pull in opposite
directions. First, restricting the primary comparison to determined-make incidents is
the construct-valid choice (§2.6) — it costs sample size (66 incidents rather than a
broader but conceptually muddled 104) in exchange for a comparison where the conditioning
variable (which make) is actually well-defined on both sides. Second, *if* Tesla's brand
is ascertained more completely than other makes — which is exactly what "a Tesla's brand
is nearly always established" implies — then the population this restriction produces is
not a random sample of all crashes: it is enriched, on the non-Tesla side, for cases
where *somebody* found the brand worth mentioning at all, which plausibly correlates with
the brand also being distinctive or notable enough to reach the headline. If so, the
reported non-Tesla rate is itself pushed **up** by this selection, meaning the true gap
between Tesla and an unselected population of "all crashes, regardless of whether the
make was nameable" could be larger than what is reported here, not smaller.

This argument rests on an assumption that cannot be independently verified from within
this dataset: that Tesla's ascertainment rate is close to complete, so that almost none
of the 108 undetermined-make candidates are secretly unidentified Teslas. The assumption
is plausible — all 3 confirmed Tesla incidents were identified without any difficulty,
consistent with Tesla's distinctive design and outsized cultural profile — but it is an
inference, not a measured fact. By construction, an incident with an undetermined make
has no source establishing what car was involved, which means there is no way to check
whether a handful of them were actually Teslas that simply went unmentioned this time.
If Tesla's true ascertainment rate is meaningfully below 100%, both the 3-incident Tesla
count and the direction of the argument above would need revising.

### 3.3 Robustness check: luxury-brand effect

To test whether the effect reflects "expensive/distinctive car" salience generally rather
than Tesla specifically, all non-Tesla makes were grouped into a premium/luxury category
and a mainstream category (see table for the exact split).

| Category | Headline names make |
|---|---|
| Tesla | 57.1% |
| Premium/luxury brands (BMW, Audi, Mercedes-Benz, Jaguar, Land Rover, Ferrari) | 15.4% |
| Mainstream brands (Toyota, Mazda, Kia, Ford, Holden, Honda, Nissan, Isuzu, and similar) | 0.7% |

A real luxury-brand effect exists — premium brands were named roughly 22× as often as
mainstream ones — but Tesla's rate exceeds even the luxury-brand baseline by a further
~4×. A general "expensive car" explanation accounts for only part of the observed Tesla
effect.

### 3.4 Robustness check: outlet and editorial-register effects

| Outlet | Articles | Headline names make |
|---|---|---|
| Sydney Morning Herald | 5 | 20.0%* |
| Daily Mail Australia | 51 | 15.7% |
| 9News | 55 | 1.8% |
| 7NEWS | 68 | 1.5% |
| ABC News | 8 | 0.0%* |
| news.com.au | 9 | 0.0%* |

*(small-sample outlets; interpret with caution)*

Grouped by editorial register, tabloid outlets named the make substantially more often
than broadcast outlets (13.3% vs 1.6%), an independent, real finding about editorial style.
Daily Mail Australia contributed the majority of both the tabloid volume and 2 of the 4
Tesla headline-naming instances in the whole dataset, motivating two further checks:

**Within Daily Mail Australia alone:**

| | Articles | Headline names make |
|---|---|---|
| Tesla | 2 | **100%** |
| Non-Tesla | 49 | 12.2% |

**Excluding Daily Mail Australia entirely:**

| | Articles | Headline names make |
|---|---|---|
| Tesla | 5 | **40.0%** |
| Non-Tesla | 140 | 0.7% |

(incident-clustered permutation p = 0.017)

The Tesla effect is present and statistically significant under both conditions —
including, notably, when Daily Mail Australia is excluded from the sample entirely
(40.0% vs 0.7%, incident-clustered permutation p = 0.017). That the effect survives
outside Daily Mail's tabloid house style is itself evidence that this is not simply a
Daily Mail artifact: the same pattern shows up in the broadcast and mainstream press,
not only in tabloid coverage. The signal is thinner in this slice of the data — 5 Tesla
articles, and only one of the three Tesla incidents ever drew a brand-naming headline
from a non-Daily Mail outlet — so this comparison inherits the same small-sample caveat
discussed throughout this write-up, rather than raising a separate one.

### 3.5 Robustness check: is this just a "dramatic out-of-control crash" effect?

Two of the three Tesla incidents are "out of control" narratives — a Tesla going airborne
and striking a bollard near an Adelaide mall, and a Tesla crashing into diners at a
Westfield restaurant. A plausible alternative explanation is that headlines simply name
the make more often for dramatic, out-of-control crashes generally (car goes airborne,
car ploughs into a building), and Tesla's incidents happen to be disproportionately of
that type — nothing to do with the brand itself.

Every incident was classified by whether any of its articles' headline or body text
describes an out-of-control or into-structure narrative ("crashed into," "ploughed into,"
"airborne," "out of control," "rolled," "mounted the kerb," and similar).

| | Incidents | Articles | Headline names make | Rate |
|---|---|---|---|---|
| Out-of-control — Tesla | 2 | 5 | 3 | **60.0%** |
| Out-of-control — Non-Tesla | 38 | 122 | 6 | **4.9%** |
| Not out-of-control — Tesla | 1 | 2 | 1 | 50.0% |
| Not out-of-control — Non-Tesla | 25 | 67 | 1 | 1.5% |

Restricted to only the out-of-control subgroup — the fairest comparison, since it holds
narrative type constant on both sides — Tesla is still named 60.0% of the time versus
4.9% for every other make, roughly 12× (incident-clustered permutation p = 0.0061). The
"dramatic crash" explanation is not nothing: non-Tesla out-of-control incidents are named
more often than non-Tesla non-out-of-control ones (4.9% vs 1.5%, ~3.3×), so headlines do
give dramatic crashes somewhat more scrutiny in general. But that effect is smaller than
the Tesla-specific gap within the same narrative category. If "it's just a
dramatic-crash effect" were the full explanation, Tesla's rate inside that category
should look like everyone else's. It does not.

Two concrete examples make the same point without any statistics. Both are exactly the
same narrative shape as the Tesla incidents above — a car goes out of control and crashes
into a shopfront — and in both, the make was never named in any headline:

- A car ploughed into a Canberra shopping centre, killing a four-year-old boy. The make
  was never established in any outlet's coverage, headline or body text
  ([7NEWS](https://7news.com.au/news/four-year-old-boy-dies-after-car-smashes-into-bws-store-at-canberra-shopping-centre-c-21344736)).
  This incident is itself one of the 61 excluded in §2.6 for exactly that reason.
- A car crashed into a hair salon on a busy Sydney shopping strip and burst into flames.
  The make (a Nissan, per body text) was reported but never appeared in any headline
  ([9News](https://www.nine.com.au/australia-news/campsie-crash-car-crashes-into-hair-salon-bursts-into-flames-on-busy-shopping-strip-in-sydneys-southwest-20260421-p5zpvk.html)).

Both are at least as dramatic as the Adelaide bollard or Westfield-restaurant Tesla
incidents — one involves a child's death, the other a fire — and neither cleared the bar
that both Tesla incidents cleared. "Out of control" alone is evidently not sufficient;
something about the Tesla incidents specifically pushed the make into the headline where
these comparably dramatic non-Tesla crashes did not.

This check is exploratory and post-hoc, like §3.3 and §3.4 — not part of the
pre-registered protocol. The out-of-control classification is a keyword match against
headline and body text, not a Codebook-defined field (`incident_type` is not populated
for most of this dataset), and the within-subgroup Tesla sample is thin (2 incidents, 5
articles) — read the direction and the named examples as the evidence, not the precise
percentages.

---

## 4. Discussion

The data are most consistent with an interpretation broader than "editors selectively
choose to headline Tesla." The roughly 50% brand-ascertainment gap in the raw candidate
pool (§3.2) suggests that for most crashes, whether *any* mention of the vehicle's brand
survives into coverage at all is close to incidental — dependent on whether a witness
mentions it, whether police release it, whether a reporter happens to ask. Tesla, by
contrast, appears to be reliably identified and mentioned somewhere in coverage almost
regardless of these incidental factors, plausibly reflecting the brand's distinctive
visual design and outsized cultural salience (a "household object-noun" effect,
comparable to genericized trademarks). Whether that ambient nameability then converts
into a headline appearance is a separate, downstream editorial step this dataset cannot
fully separate from the upstream "does anyone mention it at all" step — but the 57.1%
Tesla headline-naming rate, against a near-total absence of body-text-only Tesla
mentions, suggests the make is not merely known but actively surfaced to the headline,
more than the ascertainment explanation alone would predict.

This reframes, without fully resolving, the original polarized dispute: the claim that
Tesla is named more often is well-supported: the claim that this constitutes deliberate
targeting by editors, specifically, is not directly testable with this data and is not
the most parsimonious reading of it.

---

## 5. Strengths and Limitations

### 5.1 Strengths

- **Brand-agnostic discovery**, enforced programmatically and tested, avoiding the
  circularity that would invalidate a naive search-based approach.
- **Exhaustive human adjudication** of every candidate incident, with zero left
  undecided.
- **A construct-valid population definition** — the primary comparison is restricted to
  incidents with a determined vehicle make, so the conditioning variable is well-defined
  on both sides, rather than folding "make never ascertained" incidents into the
  non-Tesla group as an implicit zero.
- **Independent validation of the make-identification process** against a blind,
  hand-coded gold standard, specifically targeting the differential-misclassification
  risk that could otherwise manufacture this exact result.
- **Incident-level (not article-level) significance testing**, correctly accounting for
  non-independence between articles covering the same event.
- **Multiple, pre-specified robustness checks** (luxury-brand comparison, outlet-level
  and register-level analysis, within- and excluding-outlet sensitivity analysis) rather
  than a single unexamined topline number.
- **Full transparency of underlying data** — every incident, headline, and source link
  used in this analysis is available in the accompanying appendix.

### 5.2 Limitations

- **Small Tesla sample (n = 3 incidents).** This is the dominant limitation of the study.
  Confidence intervals on the Tesla rate are wide (25.0–84.2%), and sensitivity analyses
  (§3.4) show the result is not uniformly stable across outlet subsets, though it remains
  directionally consistent and statistically significant throughout.
- **Restricting to determined-make incidents costs sample size.** The primary comparison
  uses 66 of the 150 confirmed incidents; the other 84 either had no determinable vehicle
  make (61) or fell below the outlet-coverage threshold once fetch failures were
  accounted for (23). §3.2 argues this restriction is construct-valid and, if anything,
  biases the reported gap toward the conservative side, but it is an assumption
  (Tesla's near-complete ascertainability) that cannot be verified from within this
  dataset, and the smaller resulting sample widens every confidence interval reported
  here relative to what a larger, unrestricted population would have given.
- **Text news articles only.** This study's discovery method operates over each outlet's
  written-article index and cannot see video segments or social-media-native content.
  Two known real-world instances (a broadcast video segment and a short-form social video
  clip covering crashes relevant to this study) were confirmed absent from the dataset
  for this reason. Video and social captions plausibly have *greater* incentive toward
  brand-name salience than a full headline, given format constraints; if so, this
  limitation would again bias the reported effect downward rather than inflate it, but
  this has not been directly measured.
- **Coverage gaps at three outlets.** The Guardian, bbc.com, and Yahoo News Australia
  are excluded entirely from the source frame for the technical reasons described in
  §2.1, not from editorial judgment.
- **"Fault" not yet classified.** Whether the vehicle was the actively causal party in
  each crash (e.g., an out-of-control vehicle striking a fixed object) versus an
  incidentally-involved party has not been systematically coded across the dataset, and
  is a natural extension of this work rather than a claim made here.
- **Not peer-reviewed.** This is an independent project, methodologically documented but
  not externally reviewed. Findings should be treated as a well-supported, transparent
  first look, not a definitive conclusion.

---

## 6. Conclusion

Over a 12-month sample of Australian crash coverage, restricted to incidents where the
vehicle's make was actually determined, headlines named the vehicle's make in 57.1% of
Tesla-involved crashes versus 3.7% of crashes involving other makes — a statistically
robust gap that survives adjustment for editorial clustering, outlet-level style, and a
general luxury-brand naming effect. The result is built on a small number of Tesla
incidents and a deliberately narrowed population, and should be treated accordingly, but
across every robustness check performed, the direction and approximate scale of the
effect did not change. The most likely explanation is not a deliberate editorial policy
against Tesla specifically, but Tesla's unusually high ambient brand salience translating
into unusually complete and headline-surfaced identification, relative to the
near-anonymity most vehicle makes receive in routine crash coverage.

---

*Full incident-level data — every headline, every outlet, every link behind this
analysis — is available in the [data appendix](appendix.html). Code and full methodology
notes available on request.*
