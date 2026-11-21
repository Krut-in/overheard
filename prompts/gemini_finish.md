# Gemini CLI brief: last items before submission

You are taking over Overheard from Claude Code. Read the top of `PROGRESS.md`, then `git log --oneline -5`. Rules are in `GEMINI.md`. The repo is public: never print or commit anything under `secrets/`, and run the secret scan in step 4 before every push.

## Where things stand (4:35 PM)
- Live Gmail works from the command line: `.venv/bin/python -m overheard.gmail --fetch --parse` read 6 SAMPLE BOOKING emails from the lab inbox and parsed 6 bookings; all 6 match `data/abroad/itinerary.json` on kind, operator, number, ref and start date. The OAuth token is in `secrets/gmail_token.json`.
- The server route `POST /api/abroad/itinerary/gmail` hung: 5 of 6 Neon ingest calls returned (5 to 41 s) and the sixth never did, so the request ran past 3 minutes and was stopped.

## Steps (each ends on its check)
1. **Bound the ingest calls.** In `overheard/ingest.py`, give each Neon call a timeout of 30 s and one retry; on a second timeout, retry once on `config.HYDROGEN` with the same prompt and schema. Log the fallback through `overheard.gemini`. Add a unit test with a stubbed slow call. *Check:* `.venv/bin/python -m pytest tests -q` passes.
2. **Live route.** Start `.venv/bin/uvicorn server:app --port 8030`, run `curl -s -X POST localhost:8030/api/abroad/itinerary/gmail`, time it, then stop the server. *Check:* HTTP 200, 6 bookings, every `source` is `gmail`; note the seconds (the first call also writes a new fingerprint, about 40 s).
3. **Record it.** In `README.md` under "Honest failures (abroad)", replace the bullet starting "Gmail is wired but was not demoed live" with the measured result: 6 of 6 bookings read from the lab inbox and matched, read-only scope, the route time, and the ingest timeout fix. Add a row to `GEMINI_MODEL_TESTS.md` section 1.6 for this Gemini CLI run. Update the top of `PROGRESS.md`. *Check:* `git diff --stat` lists only `overheard/ingest.py`, the test file, `README.md`, `GEMINI_MODEL_TESTS.md` and `PROGRESS.md`.
4. **Ship.** `git add` those files only, run `git diff --cached | grep -nE "AIza[0-9A-Za-z_-]{20}|GOCSPX|ya29\.|refresh_token"` and expect nothing, then commit and `git push origin main`.

If a step fails, report the exact error and stop.
