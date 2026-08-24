# Seed examples — motivating cases, NOT study data

These are the incidents that prompted the hypothesis. They serve two purposes:

1. **Pipeline validation.** The brand-agnostic harvest (Protocol §6.1) must find them.
   If it misses a five-fatality crash that was national news, the harvest is broken and
   Phase 1 does not proceed.
2. **Prior elicitation.** Writing down what we expect to see *before* looking makes it
   harder to explain away a result afterwards.

**They are excluded from the analysis dataset (Protocol §13).** Incidents recalled by
the person who formed the hypothesis are the most biased sample obtainable — including
them would smuggle in exactly the recall bias the study is designed to test. Their
exclusion appears in the flow diagram.

## ⚠️ Every fact below is UNVERIFIED and must be checked before use

The details in this table are working recollections, not sourced findings. Before Phase 0
completes, each row must be verified against a Tier 1 source (police media release,
coronial finding, or court record) and the source recorded. Do not cite this file.

| # | Working name | Approx. date | Jurisdiction | Recalled vehicle | Recalled outcome | Verification status |
|---|---|---|---|---|---|---|
| S1 | Daylesford, Royal Hotel beer garden | Nov 2023 | VIC | SUV, believed BMW | 5 deaths | ☐ unverified |
| S2 | Auburn South Primary School | Nov 2023 | VIC | car through school fence | 1 death (child) | ☐ unverified — make unknown |
| S3 | Knox | recent | VIC | unknown | unknown | ☐ unverified — details not established |

## Why S1 is the useful one

If the recollection is right and the Daylesford vehicle was a BMW that was widely named,
that is a **premium ICE** make receiving exactly the treatment the hypothesis attributes
to Tesla. That is not a counter-example to the hypothesis — it is the reason the protocol
carries a `tesla` vs `premium_ice` contrast as a named secondary objective (Protocol
§9, secondary 2). Without it, a real "expensive/distinctive cars get named" effect would
be misread as a Tesla effect.

S2 is the useful one in the other direction: a child killed by a car at a school gate is
maximally newsworthy, and if the make was *not* in headlines, that suggests naming is
driven by something other than coverage intensity.

## Pre-registered priors

Recorded before any data are seen, so that the result can be scored against them:

| Quantity | Prior guess | Reasoning |
|---|---|---|
| Non-Tesla headline make-identification rate | 5–15% | Impression only |
| Tesla headline make-identification rate | 30–60% | The hypothesis |
| Direction of Tesla vs other-BEV contrast | Tesla higher, but by much less | Some of it is an EV-novelty effect |
| Direction of Tesla vs premium-ICE contrast | Roughly equal | Suspicion that this is largely a "distinctive car" effect |
| Probability the study reaches ≥25 Tesla incidents in 2023–2025 | ~45% | Narrow severity window; the trimmed 2021–22 years contributed few Teslas, so the loss is small but real |

If the Tesla vs premium-ICE contrast comes out null, the honest conclusion is that the
phenomenon is real but is not *about Tesla* — and the paper should say that in the title.

## Candidate Tier 1 verification sources

- Victoria Police media releases: `police.vic.gov.au/media-releases`
- Coroners Court of Victoria findings: `coronerscourt.vic.gov.au` — and the
  [coronial](https://github.com/changyang1230/coronial) findings database, which may
  already hold S1/S2 if findings have been handed down
- Court listings and sentencing remarks for any prosecuted matter
- Australian Transport Safety Bureau / state crash investigation reports where applicable

## Adding to this file

New recollected examples may be added at any time — they are not study data, so there is
no freeze. Every addition must carry the unverified flag until a Tier 1 source is
recorded, and every addition inherits the exclusion from the analysis dataset.
