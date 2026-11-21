# Gemini CLI brief: finish the live Gmail path

You are taking over Overheard from Claude Code. Read `PROGRESS.md` (top section), then `git log --oneline -10`, then `SPEC.md` ("Itinerary and Booking", API table) and `progress/B.md` and `progress/F.md`. Rules every agent follows are in `GEMINI.md`.

Goal: the phone page at `/abroad` builds the itinerary from the lab Gmail inbox, live, and the README says so with the result.

## What already exists
- `overheard/gmail.py`: read-only Gmail fetch (`gmail.readonly`). `python -m overheard.gmail --dry-run` prints the query; `--fetch --parse` runs the OAuth flow, lists booking-like mail and builds the Itinerary with Neon.
- `secrets/gmail_client.json`: a Desktop OAuth client in Google Cloud project `overheard-demo`, consent screen External in testing mode. `secrets/` is gitignored. Never print, copy or commit anything from it.
- `data/abroad/emails/send_list.json`: 6 SAMPLE BOOKING emails (subject and body; `to` is empty).
- `POST /api/abroad/itinerary/gmail` in `overheard/api_abroad.py` returns 409 until `secrets/gmail_token.json` exists.
- Python: `.venv/bin/python`. Server: `.venv/bin/uvicorn server:app --port 8000`.

## Steps
Each step ends on its check. The human does every step marked HUMAN; tell them exactly what to click, then wait for them to say done.

1. **HUMAN: add the lab account as a test user.** console.cloud.google.com, project `overheard-demo`, Google Auth Platform, Audience, Test users, Add users, the lab Gmail address, Save. *Check:* the human says it is listed.
2. **HUMAN: send the 6 SAMPLE BOOKING emails to the lab inbox.** Print each subject and body from `send_list.json` for the human to paste into new emails from their own account to the lab address. Their personal inbox is never read by any code. *Check:* the human says all 6 are sent.
3. **HUMAN plus you: consent once.** Run `.venv/bin/python -m overheard.gmail --fetch --parse`. A browser opens; the human signs in to the lab account themselves and approves read-only access (the "unverified app" screen needs Advanced, then Go to Overheard demo). *Check:* the command prints 6 booking-like messages and an Itinerary with 6 bookings whose operator, number and ref match `data/abroad/itinerary.json`. `secrets/gmail_token.json` now exists.
4. **Live route.** Start the server, `curl -s -X POST localhost:8000/api/abroad/itinerary/gmail`. *Check:* 200 with 6 bookings and `source: gmail`, and the time it took.
5. **Record it.** In `README.md`, replace the bullet "Gmail is wired but was not demoed live" under "Honest failures (abroad)" with the measured result (bookings found, fields matched, seconds). Add a row to `GEMINI_MODEL_TESTS.md` section 1.6 for this Gemini CLI run (model, task, wall time, result). Update the top of `PROGRESS.md`. *Check:* `git diff` shows only those three files plus nothing under `secrets/`.
6. **Ship.** Run `git diff --cached | grep -nE "AIza[0-9A-Za-z_-]{20}|GOCSPX|ya29\."` and expect nothing, then commit with a short message and `git push origin main`. The repo is public, so this scan is mandatory.

If a step fails, report the exact error and stop; do not work around OAuth or sign-in screens.
