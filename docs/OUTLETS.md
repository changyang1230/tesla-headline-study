# The top 10 Australian online news sources

The frame is the ten highest-readership Australian online news brands. An incident
qualifies for the study only if **at least 5 of these 10** covered it (§ Threshold below).

## Source of truth: Ipsos iris

**Ipsos iris** is the official digital audience measurement currency for Australia,
endorsed by IAB Australia; it replaced Nielsen Digital Panel in mid-2021 and publishes
monthly rankings of news brands by total audience (browser + app, all devices).

- IAB Australia release page: `iabaustralia.com.au` → Research & Resources → Ipsos iris
- Monthly "Top 10 news brands" tables are published as free summaries; the underlying
  panel data is subscription-only, but the ranked brand list is public.

## ✅ Verified against real Ipsos iris data

Pulled directly from three Ipsos iris "Top 10 News Category (excluding Weather &
Aggregators)" monthly ranking reports (March, May, June 2026 — `iris-au.ipsos.com`) and
averaged, per the standard this document set for itself. The exact #8–10 order is still
soft (see below); the top 7 are stable across all three months.

| # | Brand | Domain(s) | Owner | Register | Avg audience (000s, months present) |
|---|---|---|---|---|---|
| 1 | ABC News | abc.net.au | ABC | public | 12,529 (3/3) |
| 2 | news.com.au | news.com.au | News Corp | tabloid | 11,489 (3/3) |
| 3 | 9News / nine.com.au | 9news.com.au, nine.com.au | Nine | broadcast | 9,552 (3/3) |
| 4 | The Guardian Australia | theguardian.com | Guardian | broadsheet | 7,750 (3/3) |
| 5 | 7NEWS | 7news.com.au | Seven West | broadcast | 7,528 (3/3) |
| 6 | Sydney Morning Herald | smh.com.au | Nine | broadsheet | 6,724 (3/3) |
| 7 | SBS News | sbs.com.au | SBS | public | 5,670 (3/3) |
| 8 | Daily Mail Australia | dailymail.com | DMG Media | tabloid | 5,539 (2/3, absent May) |
| 9 | Yahoo News Australia | au.news.yahoo.com, au.yahoo.com | Yahoo | aggregator | 5,224 (2/3, absent March) |
| 10 | bbc.com | bbc.com | BBC | broadcast | 4,971 (3/3) |

Source images: `iris-au.ipsos.com/wp-content/uploads/2026/04/iris-March-26-news-ranking-PR.jpg`,
`.../2026/06/iris-May-news-ranking-V2.png`, `.../2026/07/ipsos-iris-June-26-News-ranking.png`.

## Three corrections from the previous (unverified) list

**Herald Sun and The Age dropped out.** Neither appears in any of the three months
checked — Herald Sun not once, The Age in only 2 of 3 and consistently the weakest brand
in the top 10 (avg 4,732, would rank 11th). Both were on the previous list from memory,
not from a pulled report; this is the concrete case the "verify before freezing" warning
below was written for.

**SBS News and bbc.com added.** Both are real, consistent top-10 entrants — SBS in all
three months, bbc.com in all three months. Neither was on the previous list at all.

**Daily Mail Australia's domain changed** from `dailymail.co.uk` to `dailymail.com`,
per a footnote on Ipsos's own June 2026 report. `match_outlet()` in `src/gdelt_harvest.py`
and `CROSS_DOMAIN_BRANDS` in `src/queries.py` have been updated accordingly.

**Yahoo News Australia stays included despite being an "aggregator."** Ipsos's own top-10
table explicitly excludes Weather & Aggregators, yet Yahoo News Australia still appears in
it (May, June) — so Ipsos itself treats Yahoo News as a news brand, not an aggregator,
for this purpose. It counts toward the coverage threshold like any other brand.

## Still soft — worth re-checking with a 4th month

Daily Mail Australia, Yahoo News Australia, and bbc.com are within ~600k of each other in
3-month average audience and each missing from at least one month. A 4th month (or
re-running this check closer to Phase 2) could reorder #8–10, though it is unlikely to
change *membership* of the top 10 — The Age and Herald Sun are not close.

## Yahoo News Australia dropped from data collection, 2026-08-25

Still #9 by readership per the table above — this is a **practical harvesting decision,
not a ranking correction**. Yahoo's live sitemap only ever exposes ~1 day of current
content (not a historical archive), and the Wayback Machine had only 6 snapshots of that
URL across an entire 12-month study window (~1.7% day-coverage) — versus news.com.au's
43%, itself already a partial-coverage compromise. Unlike news.com.au's gap (robots.txt-
gated but the data exists and a human can retrieve it by hand), Yahoo's gap is
unrecoverable: the historical sitemap states simply were never captured by anyone, so
there is no manual workaround.

Removed from `OUTLET_DOMAINS` in `src/gdelt_harvest.py` (`match_outlet()` no longer
recognises `au.news.yahoo.com`/`au.yahoo.com`), and existing Yahoo rows were deleted from
`harvest`/`harvest_progress`, not just excluded downstream — so there's no ambiguity later
about whether stray Yahoo data is quietly counting toward anything.

## SBS coverage gap: 2026-04 through 2026-08, accepted 2026-08-25

`src/sitemap_harvest.py` fetches SBS's own per-month article sitemap
(`sbs.com.au/news/sitemap-article-{yearmonth}.xml`). SBS's own sitemap index
(`sbs.com.au/news/sitemap-article.xml`) confirms these files simply don't exist yet for
2026-04 onward — SBS's sitemap generation is running ~5 months behind real time, not a
URL-guessing bug on our side. Checked two alternatives: `sitemap-latest.xml` (SBS's own
site) only carries the most recent ~31 URLs (2 days); `/news/feed` (RSS) is a curated
"Top Stories" feed, similarly recent and additionally not brand-agnostic (editorially
ranked, the same selection-bias problem a ranked source like Google News would have).
Wayback Machine CDX (the news.com.au/Guardian/bbc.com workaround) timed out repeatedly
(60s, no response) against sbs.com.au — same unreliable failure mode as Guardian/bbc.com.
No further recovery attempted. Net effect: SBS's contribution to the study is complete
for 2025-09 through 2026-03 (17 candidates over 7 months) and has a genuine 5-month
blind spot for 2026-04 through 2026-08, same in kind as the Guardian/bbc.com gaps —
accepted, not fixed.

## Threshold

**An incident qualifies if ≥ 5 of these 10 brands covered it.**

This is stricter than the previous rule (≥3 distinct ownership groups) and it will reduce
the number of eligible incidents — including Tesla ones, which are the binding
constraint. The tradeoff is deliberate: with a fixed 10-brand denominator, "6 of the 10
biggest outlets named the make" is a directly interpretable statement, and every incident
contributes a proportion out of a comparable base.

`MIN_OUTLETS` in `src/primary.py` carries this. If Phase 0 shows the threshold starving
the Tesla arm, dropping it to 3 is a pre-specified fallback (Protocol §10.4) — invoked and
recorded **before** any outcome comparison, not after.

## Notes on counting

- **9News and nine.com.au** are one brand for this purpose; count once.
- **Daily Mail Australia and bbc.com sit on global domains** (`dailymail.com`, `bbc.com`)
  shared with non-Australian editions. `match_outlet()` matches on the bare domain, not a
  country-specific path — it relies on every incident being Australian *by construction*
  (clustering is anchored on Australian localities, per `src/gdelt_harvest.py`), so a
  Daily Mail or BBC article that clusters to an Australian incident counts as Australian
  coverage regardless of which desk wrote it. Non-Australian coverage of a story with no
  Australian incident to cluster onto simply never enters the dataset.
- **AAP** is a wire, not a destination brand. It does not appear in the top 10 and does
  not count toward the threshold, but wire copy running under a listed brand counts as
  that brand's coverage — publishing someone else's copy under your masthead, headline
  included, is still an editorial decision.

## ABC coverage gap: 2026-07-27 onward, found 2026-08-25

Same failure pattern as the SBS gap above, on a different outlet. `src/sitemap_harvest.py`
fetches ABC's paginated `sitemap-news-{page}.xml.gz` files (pages 0–12 hold real content;
13+ are empty, per the module's own probe comment). Page 0 — the newest-content page — was
checked directly and its most recent article date is **2026-07-27**; ABC's own sitemap
system simply hasn't indexed anything published after that, not a bug in how we page
through it. Confirmed against a real, concrete miss: a Tesla-vs-bollard incident in
Adelaide's CBD (2026-08-14, "Woman treated for minor injuries after car rolls on side in
Adelaide's CBD", covered by ABC and 7NEWS) is entirely absent from `harvest` — and unlike
some earlier misses, this isn't a vocabulary gap either: the article's URL slug
(`twin-street-adelaide-cbd-crash-investigated`) matches `keyword_regex()` cleanly, so it
would have been picked up immediately if ABC's sitemap had the URL at all.

Checked ABC's "Just In" RSS feed (`abc.net.au/news/feed/51120/rss.xml`) as a backfill
option: live and current, but only ~25 items deep, all same-day — a rolling recent feed
like SBS's `sitemap-latest.xml`, not a month-long archive. No backfill attempted via
Wayback CDX for this gap yet (worth trying given the news.com.au/SBS precedent of mixed
CDX reliability). Net effect: ABC's contribution to the study has a real, ~4-week blind
spot for late July–August 2026, same in kind as the SBS gap — accepted for now, not fixed.
Going forward, re-running the ABC harvest periodically will catch new content as ABC's own
sitemap catches up, so this gap should shrink for future incidents even without a backfill.
