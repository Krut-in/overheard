# Gemini model tests and deliberate variations

A running log of how the Gemini 4 models behave in this project. Part 1 holds measurements already taken. Part 2 lists the variations we will inject on purpose while prompting, coding, testing and trying Overheard, with how to score each one. Add a row every time you run one.

Setup for every run unless noted: Gemini CLI 0.70.0, project folder `cv-gemini`, key from `.env`, default model `gemini-4-neon` from `.gemini/settings.json`. Latency is wall-clock from a laptop on venue Wi-Fi, so treat small gaps as noise.

## Part 1: results (measured 2026-11-21, around 2:00 PM)

### 1.1 Gemini CLI acceptance checks

| # | Test | Result | Time |
|---|---|---|---|
| T1 | `gemini -p "Reply with OK and the model you are"` | Pass. Answered "OK" and said its exact model ID was not exposed to it. | 7.5 s |
| T2 | `gemini skills list` | Pass. All 11 project skills listed with a location inside `.agents/skills/`. | 2.2 s |
| T6 | T1 again with `--output-format json` | Pass. `stats.models` reports `gemini-4-neon`, which is the reliable way to confirm the model. | about 7 s |
| T7 | "Which file must every agent update before stopping, and what is the project called?" | Pass. "PROGRESS.md" and "Overheard", so the new `GEMINI.md` is loaded. | 6.4 s |
| T8 | Hydrogen: "Use the grilling skill on this plan: ship Overheard with audio only" | Pass. It read the skill and `SCOPE.md` (6 `read_file` calls) and answered in the skill's numbered ❓/➡️ round format. | about 10 s |

### 1.2 Model sweep: same prompt, model forced with `-m`

Prompt: "Reply with OK and the model you are".

| Model | Answer | Time |
|---|---|---|
| `gemini-4-hydrogen` | "OK. Gemini." | 4.7 s |
| `gemini-4-argon` | "OK. I am Gemini." | 8.2 s |
| `gemini-4-neon` | "Exact model version ID is not exposed" | 7.5 s |
| `gemini-4-carbon` | "Gemini 3.1 Pro" (wrong) | 7.2 s |

Carbon named an older model. Plain-text self-identification is unreliable on every tier, so log the model from the API response or CLI JSON stats, never from the model's own words.

### 1.3 Skill routing

| Prompt (reply with the skill name only) | Picked | Correct |
|---|---|---|
| "Add a feature test-first with red-green-refactor" | `tdd` | yes |
| "Something is throwing intermittently in production" | `diagnosing-bugs` | yes |
| "List every agent skill available to you" | 29 names | partial |

The list in the last row mixed project and user-level skills and left out `tdd`, `research` and `writing-for-agents`, which the routing prompts found anyway. Use `gemini skills list` as the source of truth for what is installed.

### 1.4 Thinking-level tweak on Neon (REST, 120-word pitch)

| `thinkingLevel` | Thought tokens | Output tokens | Latency |
|---|---|---|---|
| default | 2,831 | 158 | 27.3 s |
| `low` | 2,076 | 171 | 20.0 s |

`low` saved 27% here. The 77 s to 18 s drop in `MODELS.md` came from a 400-word output, so the saving grows with output length. Even on `low`, Neon still spent about 2,000 thought tokens on a short pitch.

### 1.5 Coding task: prompt style against model

Task: write `parse_duration("1h30m") -> 5400` with `ValueError` on bad input. Graded by running 10 checks (5 valid strings, 5 malformed ones). Both models on `thinkingLevel: low`.

| Model | Prompt style | Checks passed | Latency | Thought tokens |
|---|---|---|---|---|
| `gemini-4-hydrogen` | terse ("Output only the code") | 10/10 | 3.7 s | 504 |
| `gemini-4-hydrogen` | structured (role, task, constraints, output) | 10/10 | 3.6 s | 555 |
| `gemini-4-neon` | terse | 9/10 | 14.3 s | 1,210 |
| `gemini-4-neon` | structured | 10/10 | 11.1 s | 990 |

Neon's terse miss was `"30m1h"`, which it accepted. The terse prompt never said units must come in h, m, s order, and the structured one did. The miss came from our prompt, and it is the kind of gap that will bite the Hydrogen question-expansion step.

### What this means for the build
1. Hydrogen is about 3x faster than Neon on small, well-specified code and was just as correct. Give it the high-volume steps the scope already assigns it.
2. State every constraint in the prompt. A missing rule cost a check even on the stronger model.
3. Log the model ID from response metadata. Self-reports were wrong or empty on all four models.
4. The stderr "Skill conflict detected" lines are harmless. Project skills in `.agents/skills/` override same-named user-level copies in `~/.agents/skills/`, which is the behaviour we want.

### 1.6 Build runs for the abroad pivot

| Ticket | Model and mode | Task | Wall time | Result |
|---|---|---|---|---|
| B | `gemini-4-hydrogen`, Gemini CLI headless, prompt on stdin, JSON out, no tools | 6 SAMPLE BOOKING emails from the fixture | 20 s | 6 valid emails first try; every operator, number and ref verbatim |
| E | `gemini-4-hydrogen`, Gemini CLI headless, JSON out | 36 rehearsal scripts with labels for 6 bookings | 55.6 s | 36 balanced items, 0 of 36 labels needed fixing |
| A | `gemini-4-hydrogen` API, thinking low, 1 call per booking, 3 at once | itinerary fingerprint | 37 s cold | 279 tagged questions, 40 to 54 per booking |
| Finish | `gemini-4-neon`, Gemini CLI | Bound Neon ingest to 30 s + retry + Hydrogen fallback, add stubbed tests, verify live `/api/abroad/itinerary/gmail` | ~8 min (route 47.1 s) | 71 tests pass; live Gmail route returned HTTP 200 with 6/6 `gmail` bookings (9 s ingest + 37 s fingerprint, 297 questions) |

## Part 2: deliberate variations to inject during the build

Each row is one change made on purpose, with everything else held fixed. Record the outcome in the last column with a time.

### 2.1 Prompting (inside Overheard's own Gemini calls)

| ID | Variation | Applies to | Score it by | Result |
|---|---|---|---|---|
| P1 | Trip extraction prompt in terse form, then with an explicit JSON schema | Neon, ticket photo to trip | fields correct on 5 tickets | |
| P2 | 50, 200 and 500 fingerprint questions per trip | Hydrogen expansion, Decision 1 | recall on relevant clips, Decision 1 latency | |
| P3 | Question wording "mentions X?" against "would a rider on trip T need to act on X?" | Decision 1 `noul` questions | precision and recall on 40 audio clips | |
| P4 | Alert threshold 0.7, 0.8 and 0.9 | relevance gate | false interruptions per 40 clips | |
| P5 | `thinkingLevel` default against `low` | Neon change extraction | latency and extracted-change accuracy | |
| P6 | Same extraction on Hydrogen, Argon and Neon | change extraction | accuracy against cost and latency | |
| P7 | `resolution: low` against default on images and video frames | Decision 1 | answer agreement and tokens used | |

### 2.2 Coding (the agent writing the code)

| ID | Variation | Score it by | Result |
|---|---|---|---|
| C1 | Same feature built by Gemini CLI (Neon) and by Claude Code, from the same `PROGRESS.md` handoff | time to a passing check, number of fix rounds | |
| C2 | Gemini CLI on `-m gemini-4-carbon` for one hard module (Carbon conflict reasoning) | fix rounds, wall time | |
| C3 | Feature request sent plain, then sent with "use the tdd skill" | did a failing test come first, test count | |
| C4 | Mid-build tool switch: stop one agent at a milestone, resume in the other from `PROGRESS.md` only | minutes until the new agent makes its first correct change | |

### 2.3 Testing (the eval harness in `SCOPE.md`)

| ID | Variation | Score it by | Result |
|---|---|---|---|
| E1 | Add venue noise to audio at rising levels | where each method's recall falls below 0.5 | |
| E2 | Add blur and glare to poster photos at rising levels | same breaking point, per method | |
| E3 | Fingerprint method against the transcribe-then-ask-Hydrogen baseline and keyword match | precision, recall, latency per modality | |
| E4 | Rerun the same eval 3 times | spread in scores, to see how much is noise | |

### 2.4 Trying the app (live demo conditions)

| ID | Variation | Score it by | Result |
|---|---|---|---|
| D1 | Spoken route against ticket photo as the trip source | trip fields correct, setup time | |
| D2 | Announcements in English, Spanish and Mandarin for the same trip | alert fired and translated correctly | |
| D3 | Two announcements overlapping | which one wins, any false alert | |
| D4 | Venue Wi-Fi against phone hotspot | end-to-end alert latency | |

## How to rerun Part 1
1. `set -a; . ./.env; set +a`
2. CLI checks: the T1 command above, plus `gemini skills list` and `gemini -m <model> -p "..." --output-format json`.
3. REST checks: POST to `.../models/<model>:generateContent` with `generationConfig.thinkingConfig.thinkingLevel` set or unset, and read `usageMetadata.thoughtsTokenCount`.
