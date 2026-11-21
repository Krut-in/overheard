# Ticket C: disruption radar

Status: done at 15:50 ET on 2026-11-21. Branch `claude/ticket-c-radar-73db6c`.

## Done, with times
| When (ET) | What | Took |
|---|---|---|
| 15:25 | Read spec, probed Hydrogen with the `google_search` tool, confirmed the grounding shape (`grounding_chunks[].web.uri` are `vertexaisearch` redirect links, `grounding_supports` map answer segments to chunks) | 10 min |
| 15:37 | Tests first for date extraction (French, Dutch, English, ranges, missing year) and URL dedupe, then `overheard/radar.py` | 8 min |
| 15:40 | First live sweep: 44 items. Fixed future `published` dates, stale pages, noisy RSS matches and one Eurostar page listed under two locales | 6 min |
| 15:47 | Added a confirm pass (two fresh 200s per URL) after bonjour-ratp.fr answered 403 two times in three | 4 min |

## How it works
- `sweep(it, today) -> [Input]` builds 8 search jobs: one per booking and one per country (FR, NL) for national strikes and weather. Each job is one `config.HYDROGEN` call with `google_search`, thinking `low`, run 8 in parallel (about 25 s for all).
- Only grounding chunks that the answer actually cites (via `grounding_supports`) become candidates. httpx follows the redirect to the real article and keeps it only on HTTP 200 with HTML.
- From the page: title (`og:title`, then `<title>`), published day (RSS date, then article meta or JSON-LD, then the date the model cited), quote and `dates`.
- The quote is the model's quoted sentence when that sentence appears word for word in the fetched page (`quote_verified: true`, 28 of 38 items). Otherwise it is the page description.
- `dates` comes from code (`extract_dates`), never from the model. It reads the title, quote, description and the cited answer text. Ranges such as "du 24 au 26 novembre" or "28 t/m 30 november" expand to each day, up to 62 days.
- RSS: NOS, nu.nl, DutchNews, franceinfo, Le Monde, 20 Minutes, Le Figaro. Each was confirmed to return dated items on 2026-11-21. NS and Schiphol have no RSS feed (404). An RSS item needs a disruption word in its title and a travel word in its title or summary.
- Dedupe by normalized resolved URL (tracking params, `www.`, trailing slash and fragment removed), and by same host plus same title. A duplicate merges its `dates` into the first item.

## Input shape (for tickets A and F)
Spec fields: `id, kind: "news", origin: "radar", mime: "text/plain", text, url, quote, published, dates, lang`.
Extra fields: `title`, `source` (host), `found_for` (booking ids whose search found it, a hint only), `via` (`search` or `rss`), `quote_verified`, and `published_src` (`rss`, `meta`, `model` or `fetched`). `fetched` means a live status page with no publication date, so `published` is the sweep day.
Snapshot file: `data/abroad/radar/snapshot_2026-11-21.json`, shaped `{today, itinerary_id, generated_at, n_items, items: [Input], searches: [{job, queries, n_sources}]}`.

## Check outputs
1. `$PY -m overheard.radar --today 2026-11-21`
```
[radar] dropped 2 URLs that did not answer 200 twice: ['https://www.actu-alt-plus.com/...', 'https://www.schiphol.nl/nl/berichten/23-en-24-november-door-staking-...']
[radar] 38 items (21 French or Dutch) in 172.1s -> data/abroad/radar/snapshot_2026-11-21.json
```
Field check on the snapshot: 38 items, none missing `url`, `published`, `quote` or `dates`. Languages: 17 en, 11 fr, 10 nl. 29 items mention a date between 23 and 30 Nov.

2. `$PY -m pytest tests/test_radar.py`
```
27 passed, 1 skipped in 0.03s
```
3. `$PY -m pytest tests/test_radar.py -m live` (the live flag is `-m live`, since a `--live` option needs a conftest outside my files)
```
1 passed, 27 deselected in 97.65s
```

## Real news found for the trip (all real, nothing fabricated)
- Regional public transport strikes in the Netherlands on 23 and 24 Nov, more announced for December (9292, FNV, NL Times, transport-online).
- Rail works between Amsterdam, Rotterdam, Brussels and Paris on 28 and 29 Nov, with EuroCity trains diverted. This weekend is when the Eurostar 9315 booking runs (rijdendetreinen.nl, NMBS b-europe.com).
- NS works in Noord-Holland on 28 and 29 Nov, and GVB Amsterdam tram diversions.
- A Paris demonstration on Saturday 28 Nov with metro stations closed (enretardchef.fr), plus marches on 25 Nov.
- A CGT strike notice for public services, Air France strike coverage, and Louvre room closures (louvre.fr).
- Weather: an NYC storm and Thanksgiving advisories around JFK for the 24 Nov flight out.

## Decisions
- Dates come from code, never from the model, so ticket A's date gate is deterministic.
- Pages published more than 90 days before the sweep day are dropped. Some status pages carry stale meta dates (2017, 2022), and those were dropped as well.
- A URL is kept only when it answers 200 on two fresh requests. That drops sites behind a bot wall, which is safer for the live check.

## Known issues
- Results change between runs because search grounding is not deterministic. The committed snapshot is the reference; rerunning overwrites it.
- 17 of 38 items are English. Some are English pages of Dutch operators (9292.nl/en, gvb.nl) and some are US sources about JFK.
- A few items are general status pages (Eurostar disruptions, GVB) whose quote is the page description, not a disruption sentence. The Eurostar page renders with JavaScript, so its real notices are not in the HTML.
- bonjour-ratp.fr and schiphol.nl items get dropped when their bot wall answers 403, so the Paris metro works for 21 to 27 Nov may be missing from a given run.
- The sweep takes about 3 minutes, mostly the confirm pass on slow hosts. Run it ahead of the demo, not live.
- `pytest` warns about the unregistered `live` mark. Registering it needs a `pytest.ini` or `conftest.py`, which ticket C does not own.
- Packages: none installed. Used httpx, feedparser and google-genai from the shared venv.
