---
layout: page
title: Does the media name the car brand more when it's a Tesla?
nav_title: Main article
permalink: /
---

*Main article · [Academic Write-up]({{ '/manuscript.html' | relative_url }}) · [Appendix]({{ '/appendix.html' | relative_url }})*

# Does the news really call out "Tesla" more than other car brands after a crash?

**Short answer: yes — a lot more. When a Tesla is involved in a crash, Australian news
headlines named the brand 57% of the time; when it was any other car (and we know what
car it was), the car make is only mentioned 3.7% of the time.**

<img src="{{ '/assets/tesla-airborne-headline-example.png' | relative_url }}"
     alt="9News headline: 'Tesla goes airborne after striking bollard near Adelaide mall', by Joseph Sahyoun, August 14, 2026"
     style="max-width:100%; border:1px solid #cccfd4; border-radius:8px; margin:20px 0;">

<p style="font-size:13px; color:#6b7078; margin-top:-14px;">One of the three Tesla
incidents in this study — one of the real headlines behind the 57% figure above.</p>

This page is the plain-English version. If you want the full methodology, every table,
and the statistical tests, [read the full write-up]({{ '/manuscript.html' | relative_url }}).
If you want to check every single crash and headline used, [see the data
appendix]({{ '/appendix.html' | relative_url }}).

## Where this question comes from

You probably remember reading news titles such as "Tesla crashes into shopfront". It's
been raised by some (including myself) that Tesla appears to be named in the news title
more than other car makes; however, others claim that such allegation is an over-reaction
based on one's personal brand allegiance, and that the brand-mention is universal and
unbiased.

Both sides are arguing from memory and vibes. Neither position is really testable just by
recalling headlines you happen to remember.

This project sets out to actually measure it. It's otherwise an arduous project, but with
the help of an LLM the process becomes feasible.

## How I tried to check it fairly

The first "natural" way to check this i.e. search the news for "Tesla crash" and "Toyota crash" and
count respective headlines **is statistically invalid**. If you search for the word "Tesla," you will
only ever find articles that already contain the word "Tesla." That guarantees the
brand shows up, before you've looked at a single real crash. It proves nothing.

Instead, I went through a fairer process:

1. **Scour through one full year of news articles on the most popular Australian news
   websites** — 7 out of the 10 most-visited news sites have full index files that could be
   read.
2. **Filter for crash-related articles generically** — words like "crash," "collision," "rolled,"
   "T-boned," "airborne" — across those seven sites, and **never search for a car brand
   name, ever, at any point.**
3. **Confirm that these are genuine car crashes** — 215 initial candidate crashes,
   checked by both an LLM and a human (myself). 65 were excluded for various reasons
   (non-Australian crashes only reported because a celebrity was involved, cases that
   turned out not to be a car crash at all, etc.), leaving 150 confirmed real crashes.
4. **Figure out what car was actually involved** by parsing the article's *body text*,
   with the headline hidden.
5. **Only keep crashes where we actually know what car it was, and where at least two
   outlets covered it.** This matters more than it sounds: for a lot of ordinary crashes,
   nobody ever bothers to say what brand the car was — it's just "a car." If we counted
   those as "didn't name the brand," we'd be comparing Tesla against a mix of real brands
   *and* cases where there's no brand to compare against in the first place. So those get
   dropped entirely, for both Tesla and non-Tesla. That leaves 66 usable crashes — 3 of
   which involved a Tesla.
6. **Only then**, ask the one real question: for every article, did the headline name
   the car's make?
7. **Compare the Tesla group against everyone else.**

Because the brand was never part of the search, and because the car's identity was
figured out from the article, the comparison isn't rigged in either
direction.

## What we found

<div style="display:flex; gap:16px; flex-wrap:wrap; margin: 24px 0;">
  <div style="flex:1; min-width:220px; border:2px solid #14161a; border-radius:12px; padding:20px; text-align:center;">
    <div style="font-size:13px; text-transform:uppercase; letter-spacing:0.05em; color:#6b7078;">When it was a Tesla</div>
    <div style="font-size:44px; font-weight:700; margin:8px 0;">57%</div>
    <div style="font-size:13px; color:#4a4f57;">of headlines named the make<br>(4 of 7 articles, 3 crashes)</div>
  </div>
  <div style="flex:1; min-width:220px; border:2px solid #cccfd4; border-radius:12px; padding:20px; text-align:center;">
    <div style="font-size:13px; text-transform:uppercase; letter-spacing:0.05em; color:#6b7078;">When it was any other car</div>
    <div style="font-size:44px; font-weight:700; margin:8px 0;">3.7%</div>
    <div style="font-size:13px; color:#4a4f57;">of headlines named the make<br>(7 of 189 articles, 63 crashes)</div>
  </div>
</div>

## But could it be something else, not "Tesla" specifically?

We checked two alternative explanations before believing this was really about
the Tesla brand.

**Maybe it's just that "expensive" or "fast" cars get named more?** Partly true — brands
like BMW, Audi, and Mercedes-Benz did get named more often than ordinary brands like
Toyota or Mazda (about 22 times more often). But Tesla's rate was still about
4 times higher again than even those luxury brands. So "expensive car" explains some of
it, but not most of it.

**Maybe it's just that dramatic, out-of-control crashes get named more, and Tesla
crashes happen to be more dramatic?** Two of the three Tesla crashes were exactly this
kind of story — a car going airborne and hitting a bollard, and a car crashing into a
restaurant. So we compared Tesla only against *other* dramatic, out-of-control crashes —
cars ploughing into buildings, going airborne, rolling. Even in that narrower, fairer
comparison, Tesla was named 60% of the time versus 4.9% for everyone else — about 12
times more.

Two real examples make this last point without needing any statistics at all. Both are
exactly the same kind of dramatic story as the Tesla crashes above, and in neither case
was the car's brand ever mentioned:

<div style="display:flex; gap:16px; flex-wrap:wrap; margin: 20px 0;">
  <div style="flex:1; min-width:260px; border:1px solid #cccfd4; border-radius:12px; padding:18px 20px; background:#f7f8fa;">
    <div style="font-size:12px; text-transform:uppercase; letter-spacing:0.05em; color:#6b7078; margin-bottom:6px;">Canberra &middot; January 2026</div>
    <div style="font-size:16px; font-weight:700; margin-bottom:8px; color:#14161a;">Car ploughs into a shopping centre</div>
    <div style="font-size:14px; color:#4a4f57; line-height:1.55;">A four-year-old boy died. Just as dramatic as either Tesla incident above — but the car's make was never reported anywhere, not in the headline, not even in the body of the article. This is exactly the kind of case explained in step 5 above: with no brand ever mentioned, it can't be counted either way, so it's excluded from the numbers rather than counted as "didn't name the brand."</div>
    <div style="margin-top:12px; font-size:13px;"><a href="https://7news.com.au/news/four-year-old-boy-dies-after-car-smashes-into-bws-store-at-canberra-shopping-centre-c-21344736">Read the source article (7NEWS) &rarr;</a></div>
  </div>
  <div style="flex:1; min-width:260px; border:1px solid #cccfd4; border-radius:12px; padding:18px 20px; background:#f7f8fa;">
    <div style="font-size:12px; text-transform:uppercase; letter-spacing:0.05em; color:#6b7078; margin-bottom:6px;">Sydney &middot; April 2026</div>
    <div style="font-size:16px; font-weight:700; margin-bottom:8px; color:#14161a;">Car crashes into a hair salon, bursts into flames</div>
    <div style="font-size:14px; color:#4a4f57; line-height:1.55;">The car was a Nissan — reported deep in the article text, but it never once made it into a headline, on any of the outlets that covered the fire.</div>
    <div style="margin-top:12px; font-size:13px;"><a href="https://www.nine.com.au/australia-news/campsie-crash-car-crashes-into-hair-salon-bursts-into-flames-on-busy-shopping-strip-in-sydneys-southwest-20260421-p5zpvk.html">Read the source article (9News) &rarr;</a></div>
  </div>
</div>

Both of those are at least as horrific and tragic as the Tesla incidents. Neither got the brand
named. 

## What this does *not* show

This is a study of **how headlines are written**, not of car safety. It says nothing
about whether Teslas crash more or less often than other cars, or whether Tesla drivers
are better or worse. It's purely about word choice once a crash has already happened and
already made the news.

It also doesn't prove journalists or editors are deliberately targeting Tesla, though an engagement incentive remains a possibility.

## The honest caveats

This entire result rests on just **seven articles from three real Tesla crashes.** That's a genuine limitation. Three incidents are not a lot, and a different twelve-month window could
plausibly have looked somewhat different. The direction and rough size of the effect held up
across every check we tried, but "held up across every check we tried, on 3 incidents"
is a different, weaker claim than "this is a large, precise, generalisable number."

This is also a personal research project, not a peer-reviewed academic study. The code,
data, and every single incident used are public and linked below specifically so anyone
can check the work rather than take it on faith — that's the whole point of publishing
the appendix alongside this. 

As a non-academic project performed in my free time, this is heavily LLM-assisted, though important steps
e.g. verification of clusters have been manually done. I have a degree in
statistics and am familiar with statistical methods. For full transparency,
I acknowledge that a large part of this write-up's prose was drafted with LLM
assistance, though all three pages have been manually read and edited by me.

**[Read the full write-up]({{ '/manuscript.html' | relative_url }})** for the complete
methodology, every statistical test, and further robustness checks (by outlet, by
publication, and more).

**[See the data appendix]({{ '/appendix.html' | relative_url }})** for every single
crash, every headline, and every source link used in this analysis.
