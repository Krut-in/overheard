# Ticket F: integration, alerts and digest

Status at 16:10 ET on 2026-11-21: done. All five checks were run on branch `claude/ticket-f-integrate-1b417a`. Check 3 lists nothing as urgent for 22 Nov, and the reason is explained below.

Running now: uvicorn on **port 8020** (port 8000 belongs to another session's server, so I left it alone), behind the quick tunnel **https://high-cashiers-paths-asn.trycloudflare.com**. Phone page: `<url>/abroad`. Subway page: `<url>/`.

## Done (times ET)
| When | What | Took |
|---|---|---|
| 15:52 | Setup, read SPEC, TICKETS, progress A to L, the router, `alert.py`, `server.py` | 6 min |
| 15:58 | `overheard/abroad_alert.py`: `alert`, `receipt`, `carbon_check`, `digest`, `why`, `gist` | 4 min |
| 16:00 | `overheard/api_abroad.py` real mode, with fixture code kept as `_fx_*`. `server.py`: `include_router` plus `/abroad` | 4 min |
| 16:01 | `tests/test_abroad_api.py`: 4 pure digest and `why` tests, 3 real-mode route tests with Gemini stubbed. Whole suite green | 2 min |
| 16:02 to 16:06 | Live checks 1 to 5 over the tunnel, screenshot | 8 min |

## How it works
- Real mode is the default. `OVERHEARD_FIXTURE=1` brings back D's fixture feed through the `_fx_*` functions, unchanged.
- Trip routes: `/itinerary/demo` loads `data/abroad/itinerary.json`. `/itinerary/ingest` calls `ingest.parse`. `/itinerary/gmail` calls `gmail.fetch_booking_emails` then `ingest.parse(source="gmail")`. All three then run `itinerary.fingerprint`, which is cached by itinerary hash, and the demo trip loads in under 1 s.
- Gmail returns **409** with a clear message when `secrets/gmail_token.json` is missing, and never starts a browser flow from the server.
- Every input becomes an Event with status `scoring`. A worker calls `match.score` with `learn.load_learned(it_id)` through a pool of 3, so at most 3 Decision calls run at once. The verdict goes into the feed first.
- Routing: relevance of 0.8 or more is an alert. From 0.4 to 0.8, `carbon_check` runs (Carbon, thinking low, sees the input and the booking). Its `alert` makes an alert and its `silence` makes a receipt that quotes Carbon's reason. Below 0.4 is a receipt.
- An alert grows in three steps. First Neon (low) gives change, action and quote, and Hydrogen translates; the alert shows with a quote or clip proof. Then the TTS whisper lands as `whisper_url`. For photos, Nano Banana's circled image replaces the proof last.
- Receipt: a Hydrogen gist of 8 words or fewer, and `why` = `top hit <p>: <question>` for the nearest booking.
- `/rehearse`: plays `rehearsal.load()` items into the feed as real inputs (mp3 or jpg bytes). With no booking, it plays one hit and one near miss per booking, 12 items in all. With `booking_id`, it plays all 6 of that booking's items.
- `/radar`: loads the snapshot for `today`. If that is missing, it uses the snapshot from the day before. Failing both, it runs a live `radar.sweep` and saves it.
- `/digest`: scores the radar snapshot first if the feed has no radar events yet, then returns `abroad_alert.digest`.
- `/dismiss`: `learn.learn` then `learn.add_learned`; the questions are stored in `data/abroad/learned/<it_id>.json`.

## Check outputs
### 1. Relevant clip alerts, near miss gets a receipt (over HTTPS)
Three rehearsal files were posted at once to `<url>/api/abroad/input`; times are from the post:
```
  2.7s train_ams_3.jpg  scoring  rel=0.9421 booking=train_ams route=alert
  9.8s train_ams_4.mp3  silent   rel=0.7651 booking=train_ams route=carbon
 11.0s train_ams_3.jpg  alert    proof=quote
 11.9s train_ams_1.mp3  alert    rel=0.9669 booking=train_ams proof=clip
 19.5s train_ams_1.mp3  alert    whisper=/api/abroad/media/d1e619f93e.wav proof=clip
 24.5s train_ams_3.jpg  alert    whisper=/api/abroad/media/fe31659c07.wav proof=photo
```
Near-miss receipt (train_ams_4, "Eurostar 9317 cancelled, 9315 runs"):
`gist "Eurostar 9317 to Amsterdam cancelled", why "Carbon: Eurostar 9317 is cancelled, while the booked Eurostar 9315 at 09:25 is running normally."`

Result: **pass for the audio clip.** Alert, whisper and proof all arrived by 19.5 s. The board photo's alert text and quote proof arrived at 11 s. After I changed the code to publish the whisper before the photo, a rerun gave whisper at 17.8 s and the circled photo at 34.2 s. Nano Banana takes 13 to 25 s per image.

### 2. Dismiss, then the same input lands under 0.4
```
dismiss ev_52f0e7 (train_ams_4, note "that is the 9317, my train is the 9315"), 9.9 s
not 0.019 Is the disruption limited to a Eurostar train number other than 9315, such as 9317?
not 0.049 Does the input name a specific train number other than 9315 as the cancelled or delayed service?
not 0.01  Does the notice apply only to a different Eurostar service and not to train 9315?
not 0.034 Is another train number, rather than 9315, the one reported as cancelled or disrupted?
not 0.039 Does the input identify the affected train by a number other than 9315 without mentioning 9315?
reposted: train_ams_4.mp3 silent 0.3623 silence (was 0.7651)
control:  train_ams_1.mp3 alert  0.9181 alert   (true alert still fires)
```
Result: **pass.**

### 3. `GET /api/abroad/digest?today=2026-11-22`
```
{'date': '2026-11-22', 'itinerary_id': 'demo-paris-amsterdam', 'urgent': 0, 'today': 0, 'silent_count': 32, 'receipts_sample': 5}
```
Nothing is urgent for 22 Nov. The only booking that starts within 48 hours is AF 23 on 24 Nov, and no radar item hits it. The NL transport strikes on 23 and 24 Nov fall before every Amsterdam booking (28 to 30 Nov), so the date gate keeps them off `train_ams` and `hotel_ams`.

The 38 radar items gave 7 alerts and 31 receipts. Other dates, from the same scored feed:
```
2026-11-24 urgent 2: museum_louvre 0.93 (Louvre room-opening plan), hotel_paris 0.86 (metro, RER and tram closures)
2026-11-27 urgent 6: train_ams 0.54 via Carbon (Amsterdam-Rotterdam-Brussel works, amended timetable for 9315 on 28 Nov),
                     hotel_ams 0.97 / 0.91 / 0.82 (GVB trams 13 and 17 skip Westermarkt), plus the two 9315 rehearsal alerts
```
So the ticket's original check (27 Nov lists the items that hit `train_ams`) passes.

### 4. Subway page and tests
```
GET <url>/ -> 200
POST /api/trip route="Q train from Times Sq-42 St to 72 St"  -> 197 questions
POST /api/input a01.wav ("Q not running")  -> alert 0.889, Hindi whisper, after 16 s
$PY -m pytest tests -q  -> 66 passed, 1 skipped, 1 warning in 13.48s
```
Result: **pass.**

### 5. Screenshot `docs/abroad_live_375.png`
375 px, taken over HTTPS after loading the demo trip, playing the rehearsal (12 items) and posting the board photo. I looked at it. The top card is the Eurostar 9315 alert in Hindi with the circled board photo. Below it come alerts for KL 641, Hotel Canal, Eurostar 9315, the Louvre, Hotel Marais and AF 23, then the trip timeline, then the "heard and let go" receipts with Carbon's reason.

Rehearsal results (expected booking, then what happened): 11 of 12 right.
```
flight_out_1 alert 0.91 | hotel_paris_1 alert 0.94 | museum_louvre_1 alert 0.96 | train_ams_1 alert 0.92 | hotel_ams_1 alert 0.88 | flight_home_1 alert 0.92
flight_out_4 silent (Carbon) | hotel_paris_4 silent (Carbon) | museum_louvre_4 silent (Carbon) | train_ams_4 silent 0.36 | hotel_ams_4 silent (Carbon)
flight_home_4 FALSE ALERT 0.8002 (KL 641 "no change, on time"; it sits right on the 0.8 line, so Carbon never saw it)
```

## Gemini calls (`logs/calls_F.jsonl`, 194 calls, 0 errors)
| Model | Calls | Median s |
|---|---|---|
| gemini-decision-1 | 63 | 0.92 |
| gemini-4-hydrogen (gist, translate, learn) | 63 | 3.0 |
| gemini-4-neon (change, low) | 27 | 6.1 |
| gemini-4-carbon (band, low) | 18 | 3.7 |
| gemini-3.8-flash-tts | 20 | 7.1 |
| gemini-nano-banana-2.1 | 3 | 13.4 |

## Decisions
- "Within 48 hours" counts calendar days: the booking's start date is today, tomorrow or the day after. A daily digest reads better that way than with a clock cutoff that depends on the hour it runs.
- "Today" in the digest means alerts on bookings active that day that are not already urgent.
- Radar falls back to the previous day's snapshot before a live sweep, because the sweep takes about 3 minutes and the snapshot is from 21 Nov.
- Rehearsal without a booking plays 12 items, not 36, to keep the feed readable and the TTS calls few.
- Rehearsal inputs carry `expected_booking` (from the labels) so the UI or evals can show right and wrong. The model never sees it.
- The alert shape adds `quote`, `whisper_text` and, for photos, `proof.original_url` to the SPEC fields.

## Known issues
- **Learned questions shave true alerts.** After the 9317 dismissal, the true board photo for 9315 fell from 0.94 to 0.78. Carbon then kept it as an alert, so the outcome held, but the guard in `learn.py` does not stop it. Ticket G should measure this.
- `flight_home_4` false alert at exactly 0.8002: Neon wrote "no change". A small fix would be to send the 0.80 to 0.85 band through Carbon too, or to drop the alert when Neon finds no change.
- The circled photo takes 13 to 34 s. The quote proof and the whisper arrive first.
- The first `/digest` on an empty feed scores 38 radar items and takes about 60 s. Cloudflare's quick tunnel cut that request at 20 s, though scoring finished on the server and a second call answered in 2 s. Press the radar button before opening the digest.
- `data/abroad/learned/demo-paris-amsterdam.json` (from check 2) is in this worktree only and not committed. Delete it to reset the demo.
- State lives in memory: restarting the server clears the feed.
