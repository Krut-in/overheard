# Ticket D: phone UI and router (fixture mode)

Status at 15:48 ET: built and checked on localhost. The ngrok check is blocked because this Mac has no ngrok auth token.

## Done (times ET)
- 15:35 to 15:38: read SPEC, TICKETS, GLOSSARY and the subway page. Drew the proof photo with Pillow and voiced the Hindi whispers and two announcements with macOS `say` (`web/abroad/make_media.py`, no Gemini calls).
- 15:38 to 15:40: `web/abroad/fixture_feed.json`. Six starting events on the demo trip: two alerts on `train_ams` (board photo with Hindi translation and circled proof, plus a radar strike notice with a quoted line), four silence receipts (French TER announcement, Dutch sprinter announcement, Louvre poster, RATP strike on 3 Dec that misses the Paris dates). It also holds three radar items and three rehearsal items that play into the feed on button press.
- 15:40 to 15:41: `overheard/api_abroad.py` with every route in the SPEC table, and `abroad_dev.py`.
- 15:41 to 15:44: `web/abroad/index.html`, vanilla HTML, CSS and JS, 375 px first.
- 15:44 to 15:47: curl check of every route, the 375 px screenshot, and a click-through in the browser (dismiss, rehearse).

## Check 1: every route in fixture mode
Command: `OVERHEARD_FIXTURE=1 .venv/bin/uvicorn abroad_dev:app --port 8010`, then a curl per route.
```
GET  /abroad -> 200 text/html; charset=utf-8
POST /itinerary/demo -> {id, traveller, home_lang, bookings, n_questions}
    bookings [0] = {id, kind, title, operator, number, ref, start, end, from_place, to_place, city, country, langs, details, source}
POST /itinerary/ingest -> {id, traveller, home_lang, bookings, n_questions}
    bookings [0] = {id, kind, title, operator, number, ref, start, end, from_place, to_place, city, country, langs, details, source}
POST /itinerary/gmail -> {id, traveller, home_lang, bookings, n_questions}
    bookings [0] = {id, kind, title, operator, number, ref, start, end, from_place, to_place, city, country, langs, details, source}
POST /itinerary/demo (reset) -> {id, traveller, home_lang, bookings, n_questions}
    bookings [0] = {id, kind, title, operator, number, ref, start, end, from_place, to_place, city, country, langs, details, source}
GET  /itinerary -> {id, traveller, home_lang, bookings, n_questions}
    bookings [0] = {id, kind, title, operator, number, ref, start, end, from_place, to_place, city, country, langs, details, source}
POST /lang -> {"lang":"Hindi"}
POST /input -> {id, t, status, input}
GET  /feed -> {itinerary_id, lang, fixture, events}
    events [0] = {id, t, status, input}
POST /radar -> {"n_items":3}
POST /rehearse -> {"n_items":3}
POST /dismiss -> {added}
    added [0] = {id, booking_id, group, q}
GET  /digest?today=2026-11-27 -> {date, itinerary_id, urgent, today, silent_count, receipts_sample}
    urgent [0] = {id, t, status, input, verdict, alert}
GET  /media/proof_train_ams.jpg -> 200 image/jpeg 130463B
GET  /media/whisper_train_ams.m4a -> 200 audio/mp4 77798B
GET  /media/..%2fserver.py (traversal) -> 404
GET  /feed after playback -> 13 events {'silent': 10, 'alert': 2, 'dismissed': 1}
```
Result: pass. Every route answers with the SPEC shape, and media names with path tricks get a 404.

## Check 2: 375 px screenshot over ngrok HTTPS
- `ngrok http 8010` fails: `authentication failed: This ngrok session is not authenticated`. No `ngrok.yml` and no `NGROK_AUTHTOKEN` on this Mac. Per the brief I did not sign up for anything.
- Fix for whoever has the account: save the token with the CLI's `config add-authtoken <token>` subcommand.
  Then run `ngrok http 8010` and rerun the screenshot against `<https-url>/abroad`.
- Meanwhile `docs/abroad_375.png` is taken from `http://localhost:8010/abroad`. It shows the timeline of 6 bookings, 3 receipts above the dock (4 in the feed), the board alert with the circled photo, Whisper and "Not about me" buttons, and the second alert.
- Headless Chrome clamps `--window-size=375,...` to a 500 px layout viewport (measured `innerWidth=500`), so that command cannot give a phone layout. `web/abroad/shot.py` emulates a 375 px mobile viewport over the DevTools protocol instead (measured `375x1600 scrollW=375`): `.venv/bin/python web/abroad/shot.py http://localhost:8010/abroad docs/abroad_375.png`.

## Decisions
- `POST /itinerary/demo`, `/ingest` and `/gmail` return the Itinerary with an extra top-level `n_questions`. `GET /itinerary` returns the same, or 404 before a trip is set.
- `GET /feed` adds `lang` and `fixture` next to `itinerary_id` and `events`.
- Each route calls one `_engine_*` function in `api_abroad.py`. With `OVERHEARD_FIXTURE` unset they raise `EngineMissing` and the route answers 503, so ticket F only swaps those function bodies.
- `POST /radar` and `POST /rehearse` play fixture items into the feed as `scoring`, then resolve them about a second apart.
- `POST /input` saves the upload to a temp folder (served under `/media/`) and returns a `scoring` Event. In fixture mode it resolves to a receipt marked "not scored" because nothing real scores it.
- `/media/{name}` looks in `web/abroad/media/`, the upload temp folder, `data/abroad/media/` and `data/abroad/rehearsal/`, so engine output can land in `data/abroad/media/` without router changes.
- News URLs in the fixture point at `example.org/fixture/...` on purpose, so the public repo never shows made-up articles under a real outlet's domain.
- Page: the newest alert is large with its proof. Older alerts are compact cards that still have Whisper and "Not about me". Dismissed alerts drop into the receipts list, struck through. The Whisper button plays `whisper_url` and falls back to the browser's speech synthesis when there is none.

## Known issues
- Fixture alerts only carry Hindi translations. Picking English shows the English text; picking another language still shows Hindi until the engine translates live.
- Auto-playing the whisper on a new alert needs a prior tap on the page (browser autoplay rules).
- The mic button needs HTTPS on a phone, so it waits on ngrok.

## For ticket F
- Mount with `app.include_router(router)` from `overheard.api_abroad`, and add a `/abroad` route serving `web/abroad/index.html`.
- Replace the bodies of `_engine_demo`, `_engine_ingest`, `_engine_gmail`, `_engine_score`, `_engine_radar`, `_engine_rehearse`, `_engine_learn` and `_engine_digest`.
