# Ticket E: rehearsal data

Branch `claude/ticket-e-rehearsal-77862b`. State: done. All three done-when checks pass.

## Done
| Step | What | Time |
|---|---|---|
| 1 | Gemini CLI on Hydrogen wrote 36 scripts with labels in one headless call | 55.6 s wall |
| 2 | Read all 36 labels by hand; fixed 0 labels. Restored French accents on all 15 French scripts with one Hydrogen API call each, kept only when the accent-stripped text matched the original exactly (15 of 15 kept) | about 7 s in parallel |
| 3 | `overheard/rehearsal.py`: `rehearse`, `load`, `check`, `write_scripts`, `voice`, `draw`, `media` | |
| 4 | Media: 24 mp3 announcements (`gemini-3.8-flash-tts`), 12 JPEG signs (`gemini-nano-banana-2.1`, 4 at once) | 60.7 s wall, 0 failures, 4.5 MB total, largest JPEG 109 KB |
| 5 | In-product path check: `write_scripts` on the Eurostar booking through the Hydrogen API gave 6 items, 3 relevant, 3 near misses | 7.3 s |

## Gemini CLI row (also belongs in `GEMINI_MODEL_TESTS.md`, which ticket E does not own)
| Model | Prompt summary | Wall time | Items | Labels fixed |
|---|---|---|---|---|
| `gemini-4-hydrogen` (confirmed by `stats.models` in the CLI JSON) | itinerary inline; 6 items per booking (4 audio, 2 image), 3 hit and 3 near miss each, the change to use per booking, near-miss kinds, language mix, full label object per item; print JSON only, no tools | 55.6 s | 36, balanced 3 of 6 on every booking | 0 of 36 |

Command: `gemini -m gemini-4-hydrogen --approval-mode yolo --output-format json -p "<prompt>"`, run from the worktree root with `GEMINI_API_KEY` exported from `.env`. The first try failed in 1 s with auth error 41: the CLI needs the key in its environment and a trusted folder (the scratchpad was untrusted, so yolo dropped to default).

## The set
- 36 items, 6 per booking, 24 audio and 12 image. Languages: 15 French, 9 Dutch, 12 English.
- Label rule: an item is relevant to a booking only when it changes that booking directly (its service, gate, entrance, station or stop on its dates). Every item labels all six bookings; each item is true at most for its own booking.
- Near misses lean hard: many name the booking and say it runs normally (for example "Eurostar 9317 cancelled, 9315 runs normally"). A keyword matcher will fire on these, which is the point.
- Files: `data/abroad/rehearsal/scripts.json` (scripts and labels, no media), `items.json` (same plus `media`), and `<id>.mp3` or `<id>.jpg` beside them.

## Check outputs
Done-when 1, `items.json`:
```
36 items {'audio': 24, 'image': 12} {'fr': 15, 'en': 12, 'nl': 9}
relevant per booking: {'flight_out': '3/6', 'hotel_paris': '3/6', 'museum_louvre': '3/6', 'train_ams': '3/6', 'hotel_ams': '3/6', 'flight_home': '3/6'}
```
Done-when 2, `$PY -m pytest tests/test_rehearsal.py -v`:
```
tests/test_rehearsal.py::test_check_flags_unbalanced_set PASSED          [ 25%]
tests/test_rehearsal.py::test_schema_and_balance PASSED                  [ 50%]
tests/test_rehearsal.py::test_size_and_mix PASSED                        [ 75%]
tests/test_rehearsal.py::test_media_exists_and_plays PASSED              [100%]
============================== 4 passed in 2.91s ===============================
```
Done-when 3: the Gemini CLI row is above.

Signs spot-checked by eye: `train_ams_3.jpg` and `museum_louvre_6.jpg` render their text exactly, accents included.

## Decisions
- Scripts came from Gemini CLI as the ticket says; `rehearse()` uses the Hydrogen API instead (one call per booking, JSON schema), since the product cannot shell out to a CLI.
- Cross-booking effects (a cancelled Eurostar delaying hotel check-in) are labelled false; only direct changes count. Ticket G should score against the same rule.
- Audio is 48 kbps mono mp3; signs are at most 1024 px JPEG, quality stepped down until under 300 KB.

## Known issues
- `train_ams_3.jpg` shows a hall with an NS (Dutch) train behind the Gare du Nord board. The text is right, the scenery is not.
- Only 2 of 12 signs were checked by eye. The other 10 may misspell a word; ticket G should look at any sign that scores wrong before blaming the matcher.
- The CLI row belongs in `GEMINI_MODEL_TESTS.md`, which this ticket does not own. The orchestrator can copy it from here.
- TTS pads clips with silence (one sentence came out at 13.6 s). Harmless for scoring, slower for a live demo.
