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

## ⚠️ Verify before freezing

The list below is the tier that consistently occupies the top 10, but **the exact
ordering moves month to month and I have not verified it against a current release.**
Before Phase 2:

1. Pull the most recent Ipsos iris monthly news-brand ranking.
2. Take the top 10 Australian news brands by total audience.
3. Fill in the `audience` column with the figure and the month.
4. Replace any brand below that the current data excludes, and record the swap in
   CODEBOOK.md §5.

Averaging the rankings over three or four consecutive months is worth the extra ten
minutes — single months bounce around on the back of one big story.

| # | Brand | Domain(s) | Owner | Register | Audience (fill in) |
|---|---|---|---|---|---|
| 1 | news.com.au | news.com.au | News Corp | tabloid | |
| 2 | ABC News | abc.net.au | ABC | public | |
| 3 | 9News / nine.com.au | 9news.com.au, nine.com.au | Nine | broadcast | |
| 4 | Daily Mail Australia | dailymail.co.uk/auhome | DMG Media | tabloid | |
| 5 | 7NEWS | 7news.com.au | Seven West | broadcast | |
| 6 | Sydney Morning Herald | smh.com.au | Nine | broadsheet | |
| 7 | The Guardian Australia | theguardian.com | Guardian | broadsheet | |
| 8 | Yahoo News Australia | au.news.yahoo.com, au.yahoo.com | Yahoo | aggregator | |
| 9 | The Age | theage.com.au | Nine | broadsheet | |
| 10 | Herald Sun | heraldsun.com.au | News Corp | tabloid | |

## Two corrections from the previous list

**Daily Mail Australia was missing.** It is consistently a top-5 Australian news site by
audience and is exactly the kind of outlet most inclined to put a brand name in a
headline. Leaving it out would have biased the study *toward finding nothing* — dropping
the outlets most likely to produce the effect.

**Yahoo News Australia was excluded as an "aggregator."** On readership grounds that was
wrong; it is a top-10 news destination for Australian readers. It is included, and flagged
`aggregator` so syndicated copy can still be identified — but it counts toward the
coverage threshold.

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

- **SMH and The Age are separate brands** but share Nine newsroom copy, so an incident
  covered by both often reflects one editorial decision. They count separately toward the
  threshold (they are separately-ranked brands) but `outlet_group` marks them as Nine so
  the syndication check can find near-duplicates.
- **9News and nine.com.au** are one brand for this purpose; count once.
- **Daily Mail Australia** sits on a `.co.uk` domain. `match_outlet()` matches on the
  `/auhome` path and the AU-specific article URL patterns, not the bare domain, so UK
  articles are not swept in.
- **AAP** is a wire, not a destination brand. It does not appear in the top 10 and does
  not count toward the threshold, but wire copy running under a listed brand counts as
  that brand's coverage — publishing someone else's copy under your masthead, headline
  included, is still an editorial decision.
