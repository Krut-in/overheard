# Ticket G: abroad evals

State: done. Branch `claude/ticket-g-evals-a63317`. The run below is the committed one.

## Headline
- Decision 1 at 0.8 caught 20 of 21 relevant items across all three sources. It raised 7 false alerts over 53 non-relevant items, and 5 of those 7 came from real radar news.
- Hydrogen (transcribe, then judge in text) was the most accurate method on rehearsal data, with 18 of 18 caught and 0 false alerts. It took 8.4 to 9.5 s per item against 0.8 to 1.1 s for Decision 1.
- The keyword baseline caught nearly everything and false-alerted on 26 of 53 non-relevant items, even though it read the ground-truth scripts.
- Carbon on the 0.4 to 0.8 band fixed the one missed sign and added 2 false alerts. It was a net loss on these sets.
- **Learning hurt.** On the held-out half, Carbon-band near misses dropped from 8 to 1, but true alerts at 0.8 fell from 17 to 6. See "Learning" below.

## Done
| Step | What | Time |
|---|---|---|
| 1 | Labels for 38 radar items times 6 bookings (`eval/abroad_labels.json`) | 6 min |
| 2 | Carbon review of every label through Gemini CLI | 178 s wall, ran in the background |
| 3 | `eval/abroad_eval.py all`: four methods, three sources, cached verdicts | 189 s cold, under 5 s from cache |
| 4 | Held-out learning test plus a diagnosis run on the true alerts it hurt | 27 + 11 Decision calls |

Calls this ticket made (`logs/calls_G.jsonl`): 139 `gemini-decision-1`, 119 `gemini-4-hydrogen`, 24 `gemini-4-carbon`, 0 errors.

## Done-when output: `$PY eval/abroad_eval.py all`
```
74 items, 279 fingerprint questions

source           method       caught  false  right bk  median s  carbon
rehearsal audio  decision    12 / 12    2/12     11      1.050
rehearsal audio  policy      12 / 12    2/12     11      1.404      10
rehearsal audio  keyword     12 / 12   10/12     12      0.000
rehearsal audio  hydrogen    12 / 12    0/12     12      8.409
rehearsal signs  decision     5 / 6     0/6       5      0.829
rehearsal signs  policy       6 / 6     1/6       6      2.378       6
rehearsal signs  keyword      6 / 6     5/6       6      0.000
rehearsal signs  hydrogen     6 / 6     0/6       6      9.530
radar news       decision     3 / 3     5/35      3      0.882
radar news       policy       3 / 3     6/35      3      1.015       8
radar news       keyword      2 / 3    11/35      1      0.000
radar news       hydrogen     3 / 3     7/35      3      4.040

Learning, held out: dismissed 9 half-1 near misses once each, 41 not-questions kept
  half 2 near misses (9): false alerts 0 -> 0, Carbon band 8 -> 1
  relevant rehearsal items alerting at 0.8: 17 -> 6; fell below 0.8: flight_home_1 0.92->0.77,
  flight_home_2 0.84->0.45, flight_home_3 0.92->0.54, flight_out_1 0.91->0.75, hotel_ams_1 0.88->0.68,
  hotel_ams_2 0.92->0.38, hotel_paris_1 0.94->0.75, hotel_paris_2 0.85->0.76, museum_louvre_2 0.86->0.72,
  museum_louvre_3 0.93->0.70, train_ams_3 0.94->0.72

Decision 1 median latency over 74 calls: 0.95 s (audio 1.05, signs 0.83, news 0.88)
```
"caught" counts relevant items that alerted. "false" counts non-relevant items that alerted. "right bk" counts caught items where the alert named the labelled booking. "carbon" is how many items policy sent to Carbon. Policy latency adds Carbon time on band items only. Keyword latency is local string matching. Hydrogen latency is transcription plus the judge call. Chart: `eval/charts/abroad_summary.png`.

## How the methods work
- **(a) Decision 1 alone:** `match.score` against the demo itinerary with the cached 279-question fingerprint. Alert when relevance is at least 0.8. At most 3 calls at once.
- **(b) Full policy:** as (a), and every item at 0.4 to 0.8 goes to Carbon with the input itself (audio, image or news text), the six bookings, the rule and the top Decision hits. Carbon returns relevant, a booking and a reason. `alert.carbon_band` is written for the subway trip, so the eval has its own abroad prompt.
- **(c) Keyword baseline:** alert when the text contains a booking string (operator, number or a key place such as Westermarkt or Gare du Nord) and a disruption word in English, French or Dutch. It reads E's ground-truth scripts for audio and signs, which flatters it.
- **(d) Hydrogen:** for audio and signs, one Hydrogen call transcribes or copies the text. Then one Hydrogen text call answers yes or no for each of the six bookings. That is one judge call per item, not one per booking as the ticket suggests, which kept the run to 119 Hydrogen calls instead of about 500.

## Carbon label review (radar news)
- Command: `gemini -m gemini-4-carbon --output-format json -p "<short task>" < payload.json`. The payload held the rule, the six bookings and each item's text with my labels. `stats.models` in the CLI JSON confirms `gemini-4-carbon`: 1 request, 175.6 s, 14,693 thinking tokens.
- Result: **38 of 38 agree.** I checked agreement in code by comparing Carbon's `carbon_true` lists with my labels, not by trusting its own `agree` flag. There was nothing to settle.
- My labels: 3 relevant pairs out of 228.
  - `news_78532c9a34` for hotel_ams: GVB says no trams at Westermarkt until February.
  - `news_d332901a93` for train_ams: international timetable changed between Schiphol and Antwerpen on 28 Nov.
  - `news_96b489dff2` for train_ams: international timetable changed between Amsterdam Centraal and Brussel Zuid on 28 Nov.
- Borderline items I labelled false, and Carbon agreed:
  - `news_6830b4317a`: the NMBS notice names EuroCity, not Eurostar.
  - `news_ccf74ed096`: Louvre galleries closed for works; entry and entrance unchanged.
  - `news_493f1ea497`: line 8 skips Republique, not Chemin Vert.
  - `news_ef953149ed` and `news_d35f8cee02`: GVB pages that list tram 13 works at Overtoomse Sluis. They never name Westermarkt.
- These five borderline items account for all 5 of Decision 1's radar false alerts. A traveller might call some of them useful. A label set this small (3 relevant items) is a weak test of recall on real news.

## Learning (held out)
- Split: the 18 rehearsal near misses sorted by id, alternating into half 1 and half 2 (9 each).
- Every half-1 item at 0.4 or above (9 of 9) was dismissed once with `learn.learn`, using E's script as the input text. That kept 41 not-questions across six bookings, and all passed L's guard (`guard_max` at most 0.3).
- Half 2 plus all 18 relevant items were rescored with those questions (27 Decision calls).
- Half-2 near misses: 0 false alerts before and after. The Carbon band went from 8 to 1, which would save 7 Carbon calls.
- True alerts at 0.8 went from **17 to 6**. 11 relevant items fell below 0.8, and hotel_ams_2 fell all the way to silence (0.38).

Diagnosis (`eval/results/abroad_learning_diag.json`: one Decision call per hurt item, asking only that booking's not-questions):
1. **Mid-strength not-answers on true alerts.** Most hurt items had a top not-probability of 0.16 to 0.22. Examples: museum_louvre_2 scored 0.16 on "limited to tomorrow", train_ams_3 scored 0.17 on "limited to the Amsterdam to Paris direction". The penalty is `s x (1 - not)`, so a true alert at 0.9 needs a not-answer of only 0.12 to drop under 0.8. L's guard lets each question score up to 0.3 on true examples. With 5 to 10 questions per booking and a max over them, some question usually lands in that range.
2. **Negation misread.**
   - hotel_ams_2 says trams "do not stop at Westermarkt", yet "Does the input confirm that Westermarkt stop is unaffected?" scored 0.69.
   - flight_home_3 shows a gate change for KL 641, yet "Does the input state KL 641 is operating on schedule?" scored 0.52. The sign gives a time and no delay, so the answer is half right.
   - flight_home_2 scored 0.46 on "exclusively for a flight number other than KL 641".
3. Before and after come from two separate Decision runs, so part of each drop is run-to-run noise. The diagnosis probabilities explain most of the drops. For example, hotel_ams_2: 0.92 x (1 - 0.69) = 0.29, against 0.38 measured.

Suggested fixes for L or F (not my files): count a not-question only when it scores above about 0.5, or compare not(b) with the booking's own `affects__` answer before applying it. Also lower `GUARD_MAX` to about 0.1, and keep at most 2 to 3 questions per dismissal. 41 questions from 9 dismissals is a lot.

## Failures, with item ids
| Item | Method | What happened | Why |
|---|---|---|---|
| `flight_out_3` (sign) | decision | 0.70, missed | A French baggage sign with AF 23 and Terminal 2E. Carbon caught it in the band, so policy is right. |
| `hotel_paris_2` (audio) | decision, policy | Alert named train_ams (0.845), not hotel_paris (0.843) | Line 8 Chemin Vert closure. The shared "p change" plus Paris place questions lift train_ams to a near tie. It alerts, but on the wrong booking. |
| `train_ams_5` (audio) | decision, policy | False alert 0.81 | "Eurostar 9314 Amsterdam to Paris cancelled; 9315 runs normally." Operator, route and cancellation words all fire, and the number is the only tell. |
| `flight_home_4` (audio) | decision, policy | False alert at exactly 0.800 | "KL643 gate change; KL641 departs on time." Sits on the threshold. |
| `train_ams_6` (sign) | policy | Carbon said relevant at 0.70 | Board shows "9315 ON TIME, 9319 CANCELLED". Carbon's reason field reads only "Wait", so its structured output broke mid-thought. |
| `news_8fc3132920` | policy | Carbon said relevant at 0.77 | KLM winter cuts with no flight named. Carbon read "cancels flights until March" as covering KL 641. |
| `news_6830b4317a`, `news_ccf74ed096`, `news_493f1ea497`, `news_ef953149ed`, `news_d35f8cee02` | decision | False alerts 0.81 to 0.93 | All five are the borderline labels above: the right place and dates, with a change that misses the booking itself. |
| `news_d332901a93` | keyword | Wrong booking (flight_home) | The text names Schiphol (the KLM booking's airport) and no Eurostar string. The baseline has no sense of which service is meant. |
| `news_96b489dff2` | keyword | Missed | Names no operator or number in its list ("internationale dienstregeling", Amsterdam Centraal, Brussel Zuid). |

## Data issue found in ticket E's audio
All 24 rehearsal mp3s speak the TTS stage direction aloud before the announcement, for example "Read this as an English-speaking railway station public address announcement, clear and slightly echoey". Hydrogen's transcripts start with it on 24 of 24 clips. Decision 1 still scored the audio well, but every clip carries a non-announcement preamble, and the demo will play it. The fix belongs to ticket E: regenerate with the direction in a system instruction, or trim it from the voiced text.

## Decisions
- One item can be relevant to at most one booking, following E's sets. "Right booking" means the alert named the labelled booking.
- Learned questions stay in `eval/results/abroad_learned.json`. They are never written to `data/abroad/learned/`, so the product's learned file is untouched.
- Carbon in the eval uses its own abroad prompt. The subway `alert.carbon_band` asks about a rider's line and direction, and F owns `abroad_alert.py`.
- Verdicts are cached in `eval/results/abroad_cache_*.json`. Delete a file to redo that method.

## Files
- `eval/abroad_eval.py`, `eval/abroad_labels.json` (labels, plus Carbon's verdict and reason for each item)
- `eval/results/abroad_summary.json` (table, learning, every wrong call), `abroad_rows.json` (per item: Decision verdict, Carbon, all four outcomes, Hydrogen transcript), `abroad_learning.json`, `abroad_learned.json`, `abroad_learning_diag.json`, `abroad_run.log`, `abroad_cache_*.json`
- `eval/charts/abroad_summary.png`, `logs/calls_G.jsonl`
