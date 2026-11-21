# Tickets: Overheard abroad

Spec: `SPEC.md`. Reference data: `data/abroad/itinerary.json`. Python: `/Users/krutinrahtod/Desktop/Desktop/WEB/webCodes/latestCodee/cv-gemini/.venv/bin/python` (pytest is installed). No two tickets in the same wave own the same file.

## Dependency graph
```
wave 1 (parallel, 3:40 to 4:25)        wave 2 (4:25 to 4:45)       ship (4:45 to 4:58)
A itinerary + match ─────────────┬───> F integration + alerts ──┐
B ingest + Gmail ────────────────┤                               │
C disruption radar ──────────────┼───> G evals ─────────────────┼──> README, DEMO, public repo
D phone UI + router (fixture) ───┤                               │
E rehearsal data ────────────────┤                               │
L learning from "not me" ────────┘                               │
H1 OAuth client (orchestrator in Chrome) ──> B live Gmail fetch ─┘
```
F needs A, B, D (and C for the radar button). G needs A, C, E, L.

## Wave 1

### A. Itinerary engine
- **Goal:** the itinerary fingerprint and one-call scoring with booking tags, per the formula in `SPEC.md`.
- **Owns:** `overheard/itinerary.py`, `overheard/match.py`, `tests/test_match.py`, `data/abroad/fingerprints/`. Adds new keys to `overheard/config.py` only (append, no edits to existing lines).
- **Builder:** Claude session. It is the core seam every other ticket uses, so it needs the spec context.
- **Depends on:** nothing.
- **Done when:**
  1. `.venv/bin/python -m pytest tests/test_match.py` passes, with pure `combine` tests for the per-booking formula, the `not` group and the news date gate.
  2. `.venv/bin/python -m overheard.match --text "Greve SNCF : l'Eurostar 9315 Paris-Amsterdam du 28 novembre est supprime"` prints `train_ams` with relevance at least 0.8 and every other booking under 0.4.
  3. The same command with "Eurostar 9317" (another train) prints relevance under 0.8 for `train_ams`. The number goes in `PROGRESS.md` either way.

### B. Booking ingest and Gmail
- **Goal:** one parser for pasted text, uploaded PDFs or screenshots, and Gmail messages, all ending in an `Itinerary`.
- **Owns:** `overheard/ingest.py`, `overheard/gmail.py`, `tests/test_ingest.py`, `data/abroad/emails/`.
- **Builder:** both. Gemini CLI on Hydrogen writes the 6 sample booking emails from the fixture (one per booking, "SAMPLE BOOKING" in subject and body), and a Claude session builds and tests the parser on Neon (thinking `low`).
- **Depends on:** nothing. The live Gmail fetch waits for H1.
- **Done when:**
  1. `.venv/bin/python -m pytest tests/test_ingest.py` passes: parsing the 6 emails gives bookings that match the fixture on `kind`, `operator`, `number`, `ref` and start date.
  2. `.venv/bin/python -m overheard.gmail --dry-run` prints the Gmail search query and the scope `gmail.readonly`, without network.
  3. A row for the Hydrogen email run is in `GEMINI_MODEL_TESTS.md`.

### C. Disruption radar
- **Goal:** before the trip, find French and Dutch news that could hit a booking: strikes, cancellations, closures, weather.
- **Owns:** `overheard/radar.py`, `tests/test_radar.py`, `data/abroad/radar/`.
- **Builder:** Claude session. Inside the product, Hydrogen with Google Search grounding, one query set per booking and date, plus SNCF, NS and Schiphol news RSS where a feed exists.
- **Depends on:** nothing.
- **Done when:**
  1. `.venv/bin/python -m overheard.radar --today 2026-11-21` writes `data/abroad/radar/snapshot_2026-11-21.json` with at least 10 `news` Inputs, each with `url`, `published`, `quote` and `dates`, and at least 3 from French or Dutch sources.
  2. `.venv/bin/python -m pytest tests/test_radar.py` passes (date extraction from French and Dutch text, dedupe by URL).
  3. Every URL in the snapshot returns HTTP 200 or a redirect to a real article (checked in the test with `--live`).

### D. Phone UI and router
- **Goal:** the phone-first page and the `/api/abroad` router, rendering from a fixture feed so it does not wait on A.
- **Owns:** `web/abroad/`, `overheard/api_abroad.py`, `abroad_dev.py` (a dev app that mounts the router and the page).
- **Builder:** Claude session. It is design-heavy and needs a browser check.
- **Depends on:** nothing (uses `web/abroad/fixture_feed.json`, written to the `Event` shape in `SPEC.md`).
- **Done when:**
  1. `.venv/bin/uvicorn abroad_dev:app --port 8010` serves `/abroad`, and each route in the `SPEC.md` table answers with the right shape (`curl` against each, in fixture mode).
  2. A screenshot at 375 px width over an ngrok HTTPS URL shows the itinerary as a timeline, at least 3 silence receipts, one alert with its proof (circled photo or quoted line) and a "not about me" button. The screenshot is saved to `docs/abroad_375.png`.

### E. Rehearsal data
- **Goal:** the announcements and signs the traveller will likely meet on each booking, voiced in French and Dutch, with labels. It doubles as the abroad eval set.
- **Owns:** `overheard/rehearsal.py`, `tests/test_rehearsal.py`, `data/abroad/rehearsal/`.
- **Builder:** both. Gemini CLI on Hydrogen writes the scripts and labels in bulk (headless, JSON output). A Claude session voices audio with `gemini-3.8-flash-tts`, draws signs with `gemini-nano-banana-2.1`, and checks the labels.
- **Depends on:** nothing.
- **Done when:**
  1. `data/abroad/rehearsal/items.json` holds at least 36 `RehearsalItem`s (6 per booking, at least 24 audio), half relevant to their booking and half near misses, in French, Dutch and English.
  2. `.venv/bin/python -m pytest tests/test_rehearsal.py` passes: schema, label balance per booking, every media file exists and plays (ffprobe).
  3. A row for the Hydrogen script run is in `GEMINI_MODEL_TESTS.md`.

### L. Learning from "not me"
- **Goal:** a dismissal turns into 3 to 5 `not` questions for that booking, so the same false alert does not repeat.
- **Owns:** `overheard/learn.py`, `tests/test_learn.py`, `eval/learn_eval.py`, `eval/results/learn.json`, `data/abroad/learned/`.
- **Builder:** Claude session, with Hydrogen writing the questions inside the product.
- **Depends on:** nothing. It proves itself on the real MTA false alert already in the repo.
- **Done when:**
  1. `.venv/bin/python -m pytest tests/test_learn.py` passes.
  2. `.venv/bin/python eval/learn_eval.py` replays the real false alert from `data/real/mta_alerts_snapshot.json` ("Manhattan-bound 7 skips 111 St...", 0.79 for the Flushing trip) and prints its relevance before and after one dismissal. It passes when the after score is under 0.4 and the two true alerts in `eval/mta_eval.py` stay at 0.8 or higher. Results go to `eval/results/learn.json`.

## Wave 2

### F. Integration, alerts and digest
- **Goal:** wire A, B, C and L into the router, build alerts and receipts for bookings, and add the digest and urgent ping.
- **Owns:** `overheard/abroad_alert.py`, `overheard/api_abroad.py` (takes over from D), one `include_router` line in `server.py`, `tests/test_abroad_api.py`.
- **Builder:** Claude session (cross-module).
- **Depends on:** A, B, D. C and L for their buttons.
- **Done when:**
  1. On `main`, with `.venv/bin/uvicorn server:app --port 8000` and ngrok: posting a relevant rehearsal clip to `/api/abroad/input` gives an alert in `/api/abroad/feed` naming the right booking, with a whisper and proof, in under 20 s. A near miss gives a receipt.
  2. `POST /api/abroad/dismiss` adds `not` questions, and the same input posted again lands under 0.4.
  3. `GET /api/abroad/digest?today=2026-11-27` lists the radar items that hit `train_ams` as urgent.
  4. The subway page at `/` still works (the existing sample buttons still alert).

### G. Evals
- **Goal:** numbers and honest failures for the README.
- **Owns:** `eval/abroad_eval.py`, `eval/results/abroad_*.json`, `eval/charts/abroad_*.png`.
- **Builder:** Claude session. Carbon (Gemini CLI, `-m gemini-4-carbon`) reviews the labels of every false alert and miss, and that review is logged.
- **Depends on:** A, C, E, L.
- **Done when:** `.venv/bin/python eval/abroad_eval.py all` prints, per source (rehearsal audio, rehearsal signs, radar news): caught, false alerts, right booking named, median latency, and the before and after of learning on a held-out half. Results are saved and the summary is in `PROGRESS.md`.

## Human steps (the orchestrator drives Chrome; you sign in)
- **H1, during wave 1:** create the OAuth client (Desktop app, scope `gmail.readonly`) and the consent screen with the lab account as test user, in the Google Cloud console. You type the password and approve consent. The client file goes to `secrets/gmail_client.json` (gitignored).
- **H2, after B writes the emails:** send the 6 SAMPLE BOOKING emails from your personal account to the lab inbox. You see each draft and say yes before anything is sent.
- **H3, between 4:00 and 5:00 PM:** make `github.com/Krut-in/overheard` public, once you say "make it public".
