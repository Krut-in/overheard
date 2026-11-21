# Ticket A: itinerary engine

State: done. All three checks run; outputs below. Branch `claude/ticket-a-engine-d96a81`.

## Done
| Item | Time |
|---|---|
| Setup, read spec and subway modules | 5 min |
| `tests/test_match.py`: 9 pure `combine` tests, written first and seen failing | 5 min |
| `overheard/itinerary.py`: TypedDicts, `load`, `fingerprint` (Hydrogen, 1 call per booking, 3 at once, thinking low, cached) | 8 min |
| `overheard/match.py`: `score`, pure `combine`, CLI (`--text`, `--file`, `--news --dates`) | 8 min |
| Live checks, latency, this file | 6 min |

## Check outputs
1. `$PY -m pytest tests/test_match.py`: `9 passed in 0.86s`.
2. Eurostar 9315 text: `train_ams` 0.9775, route alert, change_type cancelled, 1.54 s, 286 questions.
   Others: flight_out 0.08, hotel_paris 0.21, museum_louvre 0.11, hotel_ams 0.29, flight_home 0.19. Pass.
3. Eurostar 9317 text: `train_ams` 0.7015, route carbon, change_type strike. Under 0.8, so it lands with Carbon
   instead of alerting. Side effect: hotel_ams 0.42 (also carbon band).

Extra live runs (same fingerprint, 286 questions):
| Input | Top booking | Score | Route |
|---|---|---|---|
| AF 23 arrives at 2E 40 min late (fr) | flight_out | 0.93 | alert |
| Tram 13 and 17 not running to Westermarkt (nl) | hotel_ams | 0.84 | alert (train_ams 0.65) |
| Louvre closed Thursday, strike (fr) | museum_louvre | 0.88 | alert |
| "Bienvenue a bord", luggage notice (fr) | none | 0.05 | silence |

Decision 1 latency: median 0.87 s over 6 text calls at 286 questions (range 0.70 to 1.54 s). No trimming needed.
Hydrogen fingerprint: 279 questions (40 to 54 per booking: operator 45, place 59, change 57, combo 118), 37 s cold,
cached as `data/abroad/fingerprints/06757c824912.json`.

## Interface (for B, C, D, E, F, G, L)
- `from overheard.itinerary import load, fingerprint, Itinerary, Booking, Input, Verdict, TaggedQuestion`
- `from overheard.match import score, combine`
- `score(inp, it, fp, learned=[]) -> Verdict`. `inp` follows `SPEC.md` Input. Audio, image and video go in as
  `data_b64` plus `mime` and are shrunk with `decide.shrink`. `news` inputs get the date gate from `inp["dates"]`.
- `combine(answers, it, fp, learned, inp, latency_s=0.0)`: `answers` maps question id to noul probability, plus
  `"change_type"` to the chosen key.
- CLI: `$PY -m overheard.match --text "..."`, `--file clip.wav`, `--news --dates 2026-11-28 --text "..."`.

## Decisions
- "p change" in the formula is shared across bookings (max over every change question), as the spec writes it
  without (b). A strike question asked for one booking counts for all.
- Abroad `CHANGE_TYPES` live in `match.py` (cancelled, closure, delay, gate, other, schedule, strike). The subway
  set in `decide.py` only talks about trains and lines.
- `affects__<id>` names the booking date as text ("28 November 2026"); matching a date string is not arithmetic.
- Question ids are `<booking_id>__<hydrogen id>`; the JSON schema pins `booking_id` to an enum of the one booking.
- `booking_id` in a Verdict is null only when every booking scores 0 (all gated out).
- New config keys appended: `FP_PER_BOOKING`, `FP_PARALLEL`, `FP_THINKING`, `NEWS_DATE_SLACK_DAYS`.
- No packages installed in the shared venv.

## Known issues
- City-level place questions ("mentions Amsterdam") let strike or tram news lift other bookings in that city into
  the carbon band: hotel_ams 0.42 on the 9317 text, train_ams 0.65 on the tram text. Carbon or a learned `not`
  question should handle these; tightening the place prompt is the next lever.
- The 9317 case sits at 0.70, not under 0.4. The operator and route questions fire; only `affects__` and the
  number-specific combo questions tell 9315 from 9317.
- `score` retries 503 itself because `gemini.timed` cannot wrap a call whose latency it must report.
