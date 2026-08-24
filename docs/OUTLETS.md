# Outlet list (frozen at Phase 2)

An article is eligible only if its outlet appears here. The list is deliberately broad —
narrowing it to "outlets I read" would reintroduce the selection problem the design
exists to avoid.

`outlet_group` matters because syndicated copy travels within a group; it is the
clustering unit for the syndication sensitivity analysis (Protocol §8.4).

| Outlet | Domain | Group | Register | Reach |
|---|---|---|---|---|
| news.com.au | news.com.au | News Corp | tabloid | national |
| The Australian | theaustralian.com.au | News Corp | broadsheet | national |
| Herald Sun | heraldsun.com.au | News Corp | tabloid | VIC |
| Daily Telegraph | dailytelegraph.com.au | News Corp | tabloid | NSW |
| Courier-Mail | couriermail.com.au | News Corp | tabloid | QLD |
| The Advertiser | adelaidenow.com.au | News Corp | tabloid | SA |
| NT News | ntnews.com.au | News Corp | tabloid | NT |
| The Mercury | themercury.com.au | News Corp | tabloid | TAS |
| Sky News Australia | skynews.com.au | News Corp | broadcast | national |
| Sydney Morning Herald | smh.com.au | Nine | broadsheet | NSW |
| The Age | theage.com.au | Nine | broadsheet | VIC |
| Brisbane Times | brisbanetimes.com.au | Nine | broadsheet | QLD |
| WAtoday | watoday.com.au | Nine | broadsheet | WA |
| 9News | 9news.com.au | Nine | broadcast | national |
| Australian Financial Review | afr.com | Nine | broadsheet | national |
| 7NEWS | 7news.com.au | Seven West | broadcast | national |
| The West Australian | thewest.com.au | Seven West | tabloid | WA |
| PerthNow | perthnow.com.au | Seven West | tabloid | WA |
| ABC News | abc.net.au | ABC | public | national |
| SBS News | sbs.com.au | SBS | public | national |
| The Guardian Australia | theguardian.com | Guardian | broadsheet | national |
| 10 News | 10play.com.au | Paramount | broadcast | national |
| The Canberra Times | canberratimes.com.au | ACM | broadsheet | ACT |
| Newcastle Herald | newcastleherald.com.au | ACM | tabloid | NSW |
| The Examiner | examiner.com.au | ACM | tabloid | TAS |
| The Border Mail | bordermail.com.au | ACM | tabloid | VIC/NSW |
| Bendigo Advertiser | bendigoadvertiser.com.au | ACM | tabloid | VIC |
| Illawarra Mercury | illawarramercury.com.au | ACM | tabloid | NSW |
| The New Daily | thenewdaily.com.au | independent | broadsheet | national |
| Crikey | crikey.com.au | Private Media | broadsheet | national |
| AAP | aap.com.au | AAP | wire | national |
| Yahoo News Australia | au.yahoo.com | Yahoo | aggregator | national |

## Notes

- **AAP is a wire, not an outlet.** Its copy appears under other mastheads. It is listed
  so that wire-origin articles can be identified and so `is_wire` can be set. AAP's own
  site is not counted as one of the "3 distinct outlet groups" required for incident
  eligibility.
- **Yahoo News Australia** carries a mix of original and syndicated copy and is coded as
  `aggregator`; it is excluded from the outlet-group count for the same reason.
- Regional ACM titles are included because a large share of Australian fatal crashes
  happen outside capital cities and a metro-only list would systematically under-sample
  regional incidents — which would matter here, because Tesla's fleet is
  disproportionately metropolitan (Protocol §12, threat 4).
- Adding an outlet after Phase 2 requires a dated entry in the Codebook rule log and a
  re-run of the harvest for the full period, not just for recent incidents.
