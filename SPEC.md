# Overheard abroad: spec

Status: draft 1, 2026-11-21 3:35 PM ET. Product decisions come from `SCOPE.md` ("Pivot: Overheard for a whole trip abroad"). Words follow `GLOSSARY.md`. Tickets live in `TICKETS.md`.

## The product in one paragraph
A traveller connects their inbox (or pastes a booking, or taps "Load demo trip"). Overheard turns every booking into one **itinerary fingerprint**: a few hundred yes/no questions, each tagged with the booking it protects. Before the trip, it sweeps French and Dutch news for strikes, cancellations and closures on the booking dates, and it runs a **rehearsal**: the announcements and signs the traveller will likely meet, voiced in French and Dutch. On the ground, every announcement, sign, board photo and short video goes through the same `gemini-decision-1` call. Overheard speaks only when an input hits a booking. It whispers the change in the traveller's language and shows proof: their photo with the line circled, or the quoted sentence from the source. Everything else leaves a **silence receipt**. When the traveller taps "not about me", Overheard writes sharper questions for that booking so the same mistake does not repeat.

## What stays as it is
The NYC subway demo (`server.py` routes under `/api/`, `web/index.html`, `overheard/decide.py`, `fingerprint.py`, `trip.py`) is the 5:00 PM fallback. No ticket edits those files except ticket F, which adds one `include_router` line to `server.py`. The abroad product lives under `/api/abroad/` and `/abroad`.

## Data model
Plain JSON-able dicts (Python `TypedDict` in `overheard/itinerary.py`). Times are ISO 8601 with offset. Ids are short snake_case.

### Itinerary and Booking
The fixture `data/abroad/itinerary.json` is the reference instance. Every ticket codes against it.

```
Itinerary = {id, traveller, home_lang, bookings: [Booking]}
Booking   = {id, kind: flight|hotel|train|ticket, title, operator, number, ref,
             start, end, from_place, to_place, city, country, langs: [iso639-1],
             details, source: gmail|upload|paste|demo}
```

### TaggedQuestion and Fingerprint
```
TaggedQuestion = {id, booking_id, group, q}
group in: operator  mentions the booking's operator or service number (AF 23, Eurostar 9315, KLM)
          place     mentions a place on the booking (CDG 2E, Gare du Nord, Westermarkt, Louvre)
          change    says there is a disruption of a type (strike, cancellation, delay, platform change,
                    closure, gate change), any language
          combo     says a disruption hits this booking's operator, number, place or date (high signal)
          not       a learned question; a yes means the input is NOT about this booking
Fingerprint = [TaggedQuestion]   (whole itinerary, 40 to 80 per booking, under 600 in total)
```
Plus one direct question per booking, id `affects__<booking_id>`, built in code from the booking fields. Questions never ask about dates in a way that needs arithmetic; date checks happen in code (`Input.dates` against booking start and end).

### Input
```
Input = {id, kind: audio|image|video|text|news, origin: mic|upload|radar|rehearsal|sample,
         mime, data_b64 | text, url?, quote?, published?, dates?: [YYYY-MM-DD], lang?}
```
`news` inputs carry `text` (title plus summary), `url`, `published` and the `dates` they mention.

### Verdict
One Decision 1 call per input returns one Verdict.
```
Verdict = {input_id, relevance, booking_id | null, per_booking: {booking_id: score},
           change_type, top_hits: [{p, q, booking_id}], route: alert|carbon|silence,
           latency_s, n_questions}
```
Scoring per booking b, with p(x) the Decision 1 probability:
```
fp(b)   = max(p operator(b), p place(b)) x max(p combo(b), p change)
not(b)  = max(p not(b)), or 0 when b has no learned questions
s(b)    = (0.3 x p affects__b + 0.7 x fp(b)) x (1 - not(b))
relevance = max over b of s(b); booking_id = argmax
route   = alert if relevance >= 0.8, carbon if 0.4 to 0.8, silence below
```
For `news` inputs, s(b) is forced to 0 when `Input.dates` is non-empty and none fall inside the booking's start date minus one day to end date. The 0.3 weight and the thresholds come from `overheard/config.py`.

### Receipt and Alert
```
Receipt = {input_id, gist, relevance, nearest_booking_id, why}       (route = silence)
Alert   = {input_id, booking_id, change, action, translated: {change, action, lang},
           whisper_url, proof: Proof, carbon?: {verdict, reason}}
Proof   = {kind: photo|quote|clip, url, quote, source_url?, t_start?, t_end?}
```
`gist` is a few words from Hydrogen. `why` names the top hit question and its score.

### Event (what the phone renders)
```
Event = {id, t, status: scoring|silent|alert|dismissed, input: Input (no data_b64),
         verdict?, receipt?, alert?}
```

### Dismissal and LearnedQuestions
```
Dismissal = {event_id, booking_id, note?}
learn(dismissal, event) -> [TaggedQuestion with group "not"]   (3 to 5, Hydrogen)
```
Learned questions are stored in `data/abroad/learned/<itinerary_id>.json` and merged into the fingerprint at score time.

### RehearsalItem
```
RehearsalItem = {id, booking_id, lang: fr|nl|en, kind: audio|image, script, media,
                 labels: {booking_id: true|false}, why}
```
Stored in `data/abroad/rehearsal/items.json` with media beside it. Half of the items per booking describe a change that hits the booking, half are near misses (another train number, the other direction, another terminal, another date).

### Digest
```
Digest = {date, itinerary_id, urgent: [Event], today: [Event], silent_count, receipts_sample: [Receipt]}
```
Urgent means relevance >= 0.8 and the booking starts within 48 hours.

## Module seams
Each module is one file with a small interface. Callers and tests cross the same interface.

| Module | Interface | Hides |
|---|---|---|
| `overheard/itinerary.py` | `load(path) -> Itinerary`, `fingerprint(it) -> Fingerprint` (cached by itinerary hash in `data/abroad/fingerprints/`) | Hydrogen prompt, schema, id dedupe |
| `overheard/match.py` | `score(inp: Input, it, fp, learned=[]) -> Verdict`, `combine(answers, it, fp, learned, inp) -> Verdict` (pure) | Decision 1 call, input shrinking, the formula above, date gate |
| `overheard/ingest.py` | `parse(texts_or_files) -> Itinerary` | Neon extraction, merge and dedupe of bookings |
| `overheard/gmail.py` | `fetch_booking_emails(creds_path, since) -> [str]` | OAuth token handling, Gmail search query, MIME decoding |
| `overheard/radar.py` | `sweep(it, today) -> [Input]` (kind news) | Hydrogen with Google Search grounding, RSS, date extraction |
| `overheard/rehearsal.py` | `rehearse(it, per_booking=6) -> [RehearsalItem]` | Hydrogen scripts, TTS voicing, sign images |
| `overheard/learn.py` | `learn(dismissal, event, it) -> [TaggedQuestion]`, `load_learned(it_id)`, `save_learned(it_id, qs)` | Hydrogen prompt for "not" questions |
| `overheard/abroad_alert.py` | `alert(inp, verdict, it, lang) -> Alert`, `receipt(inp, verdict) -> Receipt`, `digest(events, it, today) -> Digest` | Neon change extraction, translation, TTS, Nano Banana proof, Carbon band |
| `overheard/api_abroad.py` | FastAPI `router` with the routes below | in-memory session state, threading |

## API between engine and phone UI
All under `/api/abroad`. JSON in and out unless noted. The phone polls `GET /feed` every 1.5 s.

| Method and path | Body | Returns |
|---|---|---|
| `POST /itinerary/demo` | none | `Itinerary` (the fixture) and `n_questions` |
| `POST /itinerary/ingest` | multipart `files[]` and/or form `text` | `Itinerary` |
| `POST /itinerary/gmail` | none | `Itinerary` built from the lab inbox |
| `GET /itinerary` | none | current `Itinerary` |
| `POST /lang` | form `lang` | `{lang}` |
| `POST /input` | multipart `file` | `Event` (status `scoring`; result arrives in the feed) |
| `GET /feed` | none | `{itinerary_id, events: [Event]}` newest first |
| `POST /radar` | optional form `today` | `{n_items}`; items arrive in the feed as events |
| `POST /rehearse` | optional form `booking_id` | `{n_items}`; items play into the feed |
| `POST /dismiss` | form `event_id`, `booking_id` | `{added: [TaggedQuestion]}` |
| `GET /digest` | optional `today` | `Digest` |
| `GET /media/{name}` | none | whisper audio, proof images, clips |

The page is `web/abroad/index.html`, served at `/abroad`, built for a 375 px wide phone first. It must work over HTTPS (needed for the mic on a phone); the tunnel is ngrok.

## Proof that it works
Every ticket's done-when check is in `TICKETS.md`. The final eval (ticket G) reports, per source (rehearsal audio, rehearsal signs, real news):
- alerts caught and false alerts, with the right booking named;
- learning: false alerts before and after one dismissal, on held-out items;
- median latency per input.
Honest failures go in the README next to the numbers.
