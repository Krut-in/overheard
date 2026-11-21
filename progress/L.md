# Ticket L: learning from "not me"

Status: done, 2026-11-21. Started 3:34 PM ET, checks green at 3:40 PM ET (clock on this machine).

## What got built
- `overheard/learn.py` (about 25 min including the guard): `learn(dismissal, event, it)` returns up to 5 TaggedQuestions with group `not`, tagged with the dismissed booking. Hydrogen sees the input text (or quote, alert change, receipt gist), the top hit questions and the booking. `load_learned(it_id)`, `save_learned(it_id, qs)` (writes the full list) and `add_learned(it_id, new)` (appends, skips ids already stored) use `data/abroad/learned/<it_id>.json`. `not_score(p, learned, booking_id)` is not(b) from SPEC.md and `apply_not(s, not_p)` is `s x (1 - not)`, so ticket A's `match.combine` can call them.
- Guard against silencing real alerts: Hydrogen writes 5 to 7 candidates plus 3 `keep_examples` (true alerts for the booking, at least one mentioning the other direction in passing). One Decision 1 call per keep example scores every candidate, and any candidate above `GUARD_MAX = 0.3` on a keep example is dropped. Each kept question carries `guard_max`. `learn.LAST` holds the keep examples and dropped candidates from the latest run, for the UI or evals.
- `tests/test_learn.py`: 11 tests (storage round trip, append with dedupe, not(b) per booking, the factor, booking tagging, id dedupe, the guard drop, the cap at 5, unknown booking). Hydrogen and the guard are stubbed.
- `eval/learn_eval.py`: the 7 train trip (T3) is one pseudo-booking. It scores the real false alert as shown, dismisses it once, learns, then scores all 33 snapshot alerts plus 4 held-out notices with the cached fingerprint plus learned questions, one Decision call each. before = subway relevance from `decide.score`, after = before x (1 - not). Whole run takes about 15 s. Results in `eval/results/learn.json`, learned questions in `data/abroad/learned/subway_T3.json`, call log lines in `logs/calls_L.jsonl`.

## Check 1: pytest
```
$PY -m pytest tests/test_learn.py
11 passed in 0.64s
```

## Check 2: eval (latest run, the one committed)
```
[gemini] gemini-4-hydrogen 9.32s  learn not-questions

Keep examples Hydrogen wrote (true alerts for T3, used by the guard):
  - MTA service alert. Flushing-bound [7] trains are running with delays due to signal problems at Queensboro Plaza. Manhattan-bound [7] service is operating normally.
  - MTA service alert. In Queens, Flushing-bound [7] skips 103 St and 111 St due to track maintenance. For service to these stations, take the [7] to Mets-Willets Point and transfer to a Manhattan-bound [7].
  - MTA service alert. [7] trains are suspended in both directions between Grand Central-42 St and 74 St-Broadway because of a stalled train.
Dropped by the guard (fired on a keep example):
Learned questions kept (booking T3), with max p on the keep examples:
  0.01  not__T3__only_manhattan_bound: Is the service disruption or skipped stops limited to Manhattan-bound trains?
  0.01  not__T3__opposite_direction_only: Does the disruption only affect trains going in the opposite direction of Flushing-bound?
  0.01  not__T3__exclusively_manhattan_bound: Is the disruption described in the alert exclusively for Manhattan-bound service?
  0.09  not__T3__skipped_only_manhattan: Are the skipped stations only skipped by trains heading toward Manhattan?
  0.01  not__T3__problem_only_manhattan: Does the alert only report a problem for 7 trains heading toward Manhattan?

Dismissed alert scored 0.793 when shown.

       before   not  after  band after  header
FALSE   0.793  0.99  0.008  silence     'In Queens, Manhattan-bound [7] skips 111 St, 103 St, 90 St and 82 St\nA'
TRUE    0.983  0.07  0.918  alert       'In Queens, Flushing-bound [7] skips 52 St and 69 St\nAll trains at Wood'
other   0.655  0.39  0.402  carbon      '[1] runs every 8 minutes'
other   0.316  0.37  0.200  silence     '[5] runs every 20 minutes'
other   0.307  0.51  0.150  silence     '[SIR] New Dorp Station - St George-bound - east end entrance is closed'
other   0.257  0.47  0.137  silence     'Downtown [1] trains are stopping at 116 St-Columbia University, Cathed'
other   0.253  0.21  0.200  silence     'In Upper Manhattan, no [C] between 145 St and 168 St'
other   0.239  0.19  0.194  silence     'No [J] between Myrtle Av and Broad St'
other   0.231  0.98  0.003  silence     'In the Bronx, Manhattan-bound [D] skips 182-183 Sts, 174-175 Sts and 1'
other   0.229  0.19  0.185  silence     '[G] trains are delayed entering and leaving Court Sq while we address '
other   0.204  0.93  0.015  silence     'In Manhattan, downtown [4][5][6] skip 86 St'
other   0.164  0.94  0.009  silence     'In Manhattan, downtown [1] and [2] local skip 86 St, 79 St, 66 St-Linc'
other   0.162  0.19  0.131  silence     'In Southeast Queens, [H] Rockaway Park Shuttle is replaced by free shu'
other   0.154  0.40  0.092  silence     '[6] runs every 8 minutes'
other   0.140  0.29  0.099  silence     'Enter 5 Av/53 St [E][F] Station at 5 Av only - Madison Av side of stat'
other   0.137  0.35  0.089  silence     'In Brooklyn, Coney Island-bound [D] skips Fort Hamilton Pkwy, 50 St an'
other   0.135  0.28  0.098  silence     'In Brooklyn, transfer across the platform at Myrtle-Wyckoff Avs to con'
other   0.132  0.35  0.086  silence     '[2][3] runs every 12 minutes'
other   0.132  0.93  0.010  silence     'Downtown [1] skips 125 St'
other   0.128  0.94  0.008  silence     'In Brooklyn, Manhattan-bound [J] trains at Broadway Junction board fro'
other   0.119  0.97  0.004  silence     'In Manhattan, downtown [4] local and [6] skip 116 St, 110 St, 103 St, '
other   0.115  0.27  0.084  silence     'No [M] between Myrtle Av (Broadway) and Delancey St-Essex St\nAll train'
other   0.100  0.32  0.068  silence     'In Queens, all [M] trains at Fresh Pond Rd, Forest Av and Seneca Av bo'
other   0.096  0.25  0.072  silence     'In Brooklyn, all [M] trains at Central Av and Knickerbocker Av board f'
other   0.085  0.13  0.074  silence     'In Brooklyn and Manhattan, [C] service is rerouted via [D] and [F] in '
other   0.083  0.81  0.016  silence     'In Manhattan, uptown [A] stops at 23 St and 50 St'
other   0.080  0.99  0.001  silence     'In Brooklyn, Manhattan-bound [R] skips 25 St, Prospect Av, 4 Av-9 St a'
other   0.076  0.91  0.007  silence     'In Manhattan, downtown [A] stops at 50 St, 23 St and Spring St'
other   0.076  0.13  0.066  silence     'In Upper Manhattan, [A] stops in both directions at 155 St and 163 St-'
other   0.067  0.14  0.057  silence     'Uptown [A][C][F] trains are running with delays while we conduct plann'
other   0.065  0.24  0.050  silence     'In Upper Manhattan, no [A] between 168 St and 207 St'
other   0.062  0.95  0.003  silence     'In Brooklyn and Lower Manhattan, no Inwood-bound [A] at High St, Fulto'
other   0.061  0.32  0.041  silence     'In the Bronx, Woodlawn-bound [4] skips Burnside Av'

Held-out notices (hand-written, not shown to Hydrogen):
  truth=False before 0.702 (carbon) -> after 0.007 (silence)  not=0.99  held_wrong_dir_delay
  truth=False before 0.733 (carbon) -> after 0.007 (silence)  not=0.99  held_wrong_dir_suspended
  truth=True  before 0.982 (alert) -> after 0.931 (alert)  not=0.05  held_right_dir_delay
  truth=True  before 0.983 (alert) -> after 0.965 (alert)  not=0.02  held_both_dirs

Per learned question, false alert vs true alert:
  0.927 0.029  not__T3__only_manhattan_bound
   0.97 0.066  not__T3__opposite_direction_only
   0.59 0.021  not__T3__exclusively_manhattan_bound
   0.99 0.011  not__T3__skipped_only_manhattan
  0.842 0.022  not__T3__problem_only_manhattan

checks: {"false_after_under_0.4": true, "true_after_at_least_0.8": true, "no_other_alert_in_alert_band": true} PASS
```
A second full run (fresh Hydrogen questions) also passed: false alert 0.793 to 0.015, true alert 0.983 to 0.954, held-out true notices 0.972 and 0.973.

## Decisions
- Before and after come from the same Decision call (fingerprint plus learned questions in one request); "before" ignores the `not` group. `decide.score` already groups questions by `group`, so `groups["not"]` is not(b) and the subway formula is untouched.
- The guard was added after the first version: one held-out true notice ("Flushing-bound delayed, Manhattan-bound on schedule") dropped from 0.982 to 0.542 because Hydrogen wrote "Does the change apply only to trains travelling away from Flushing-Main St?" (0.45 on the true notice). The prompt now also asks for plain direction words over spatial reasoning.
- The Carbon band is not applied in this eval; it measures the Decision 1 score and the factor only.
- The T2 true alert from `eval/mta_eval.py` (F train delays) is untouched by construction: learned questions are tagged T3, and not(b) only reads questions for its own booking.

## Known issues
- The false alert is both the dismissed input and the test item, as the ticket asks. The 4 held-out notices were hand-written by the build agent, and Hydrogen's keep example 1 happens to resemble held-out notice 3, so that notice is not fully independent of the guard.
- In the two passing runs the guard dropped nothing; the main fix came from the prompt wording. The guard costs about 1 s (3 parallel Decision calls) on each dismissal.
- "[1] runs every 8 minutes" scores 0.655 for the 7 train trip before learning (a pre-existing weakness: the `line` group fires on "runs every N minutes"). After learning it sits at 0.40 to 0.47, still in the Carbon band.
- Learned questions apply to every future input for that booking, so a stale dismissal could hide a later real change of the same shape. There is no expiry or undo yet.
