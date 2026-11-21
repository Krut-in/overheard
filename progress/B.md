# Ticket B: booking ingest and Gmail

Branch `claude/ticket-b-ingest-0def97`. Status at 15:38 ET: all three done-when checks pass. Live Gmail fetch waits for H1 (the OAuth client file).

## Done
| Item | Time | Notes |
|---|---|---|
| 6 sample emails by Gemini CLI on Hydrogen | 3 min (20 s model wall time) | `data/abroad/emails/<booking_id>.txt`, plus `send_list.json` (subject and body per email, `to` empty) |
| `overheard/ingest.py` | 4 min | `parse(items, source=None, home_lang="English") -> Itinerary`. One Neon call per item (thinking low, JSON schema), run in parallel; code normalises numbers, dedupes, sets `source`, sorts by start, assigns unique ids |
| `overheard/gmail.py` | 3 min | `fetch_booking_emails(creds_dir, since) -> [str]`, scope `gmail.readonly` only, installed-app flow, token cached at `secrets/gmail_token.json` (mode 600) |
| `tests/test_ingest.py` | 2 min | 4 pure merge tests, 2 live Neon tests on the 6 emails, 2 pure Gmail tests |

## Gemini CLI row (for `GEMINI_MODEL_TESTS.md`)
| Model | Prompt summary | Wall time | Result |
|---|---|---|---|
| `gemini-4-hydrogen` via Gemini CLI headless (`gemini -m gemini-4-hydrogen --output-format json -p "<short task>" < prompt.txt`) | write 6 operator-style SAMPLE BOOKING confirmation emails from the fixture, returned as one JSON object, no tools | 20 s (3 API requests, 66k prompt tokens with 39k cached, 1.2k thinking tokens) | 6 valid emails on the first good run; every operator, number and ref present verbatim; French lines for Paris and Dutch lines for Amsterdam |

Two lessons from the run:
- A long multi-line prompt passed as the `-p` argument was ignored ("No user instruction was included in the prompt"). Piping the prompt on stdin with a short `-p` worked.
- `--approval-mode yolo` was blocked by my session's permission classifier, so Hydrogen ran with no tools and my code wrote the files from its JSON.

## Check outputs
```
$ $PY -m pytest tests/test_ingest.py -q
........                                                                 [100%]
8 passed in 18.07s

$ $PY -m overheard.gmail --dry-run
query: subject:("SAMPLE BOOKING" OR confirmation OR booking OR reservation OR itinerary OR e-ticket OR confirmee OR bevestiging OR boeking) -in:spam -in:trash after:2026/10/22
scope: gmail.readonly (https://www.googleapis.com/auth/gmail.readonly)
client: .../secrets/gmail_client.json missing
```
Neon latency per email: 6.2 to 8.4 s, all 6 in parallel, so a full parse takes about 9 s. Lines in `logs/calls_B.jsonl`.

## Decisions
- Dedupe key is the booking ref plus kind and number (one PNR can cover two legs). Without a ref, the key is kind, number (or operator) and start date. Duplicates merge field by field, keeping the longer value.
- Flight numbers are normalised in code to `AF 23` form; train numbers to digits only; hotels and tickets get an empty number.
- Ids are `<kind>_<number or city>` (e.g. `flight_af_23`, `hotel_paris`), made unique with a suffix. They differ from the fixture ids (`flight_out`), which the test does not compare.
- `source` defaults to `paste` for strings and `upload` for `(bytes, mime)`; callers pass `source="gmail"` for Gmail mail.
- `gmail.py` imports the Google auth libraries lazily, so `--dry-run` needs no network and no extra packages.
- The Gmail query matches subject terms only, newest 30 messages, last 30 days by default.

## Packages installed in the shared venv
`google-auth-oauthlib` and `google-api-python-client` (with their dependencies), via `uv pip install` because the venv has no pip.

## Known issues and next steps
- Live fetch is untested until H1 puts `secrets/gmail_client.json` in place. Then run `$PY -m overheard.gmail --fetch --parse` from the checkout that holds `secrets/` (default path is `<repo root>/secrets`, so a worktree needs `--creds-dir` pointing at the main checkout's `secrets/`). The first run opens a browser for the lab account consent.
- PDF and screenshot inputs go through the same Neon call but have no test fixture yet.
- Neon is asked for UTC offsets; a wrong offset would shift sort order but not the start date the tests check.
