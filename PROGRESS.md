# Progress

Every agent (Gemini CLI or Claude Code) updates this file after each milestone and before stopping. Newest entries go at the top of each section. Times are ET.

## Current milestone
M2 fingerprint engine and demo server (`PLAN.md`), started 2:28 PM. Build agent: Claude Code.

## Done (with time)
- 2:27 PM: M1 Decision 1 prototype passed. 3 clips and 3 posters against 3 trips: 17 of 18 right, median 0.81 s, max 1.86 s per call with about 200 questions. No false alert above 0.8; the one miss (Spanish Q announcement scored 0.60 for the F trip) lands in the Carbon band. Big lesson: shrinking inputs (16 kHz mono mp3, 1024 px JPEG) cut latency from a 3.4 s median to 0.8 s; question count barely matters. Results in `eval/prototype_results.json`. About 7 min. (Claude Code)
- 2:24 PM: M0 data. 24 TTS announcements and 18 Nano Banana posters in `data/synth/`, labels in `data/labels.json` (from `data/spec.py`). 3 trips extracted by Neon in `data/trips.json`, fingerprints by Hydrogen (191 to 213 questions) cached in `data/fingerprints/`. A subagent pulled 8 real Commons signage photos and 6 real station audio clips into `data/real/` (no real NYC PA announcements exist on Commons; clips are train noise and are unverified). About 6 min. (Claude Code)
- 2:18 PM: Grilling done. Decisions in `SCOPE.md` (new section at the bottom) and milestones in `PLAN.md`. (Claude Code)
- 2:15 PM: Tooling set up so both agents can build and hand off. Matt Pocock skills installed for both tools, `GEMINI.md` shared through `CLAUDE.md`, git initialised with a first commit, Gemini CLI checks passed (`GEMINI_MODEL_TESTS.md`). About 20 min. (Claude Code)

## Next step
Build `server.py` (FastAPI) and `web/index.html`: trip in (typed route or ticket photo) to Neon trip, Hydrogen fingerprint, then upload audio or photo to `overheard/decide.py` `score_bytes`, show silence receipts. Then `overheard/alert.py` (M3).

## Decisions made
- Relevance = 0.5 x direct `affects_trip` question + 0.5 x fingerprint score, where fingerprint score = max(line questions) x max(combo, change). Gating on the line stops look-alike station names on other lines from firing.
- Every input is shrunk before Decision 1 (`decide.shrink`). Run at most 3 Decision calls in parallel.
- Python venv at `.venv` (uv). Run things with `.venv/bin/python`.
- One instructions file: `GEMINI.md`. `CLAUDE.md` only imports it.
- Skills for Gemini CLI live in `.agents/skills/` and are pinned in `skills-lock.json`. Claude Code gets the same skills from the `mattpocock-skills` plugin.

## Known issues
- Hydrogen station-mention questions fire on similar names ("52 St" for "59 Street"). Handled by the line gate, but it is an honest failure for the README.
- `genai.Client` must be shared across threads (`overheard/gemini.py`); two clients created in a race close each other's connection pool.
- The `.agents/skills/` copies come from `mattpocock/skills` on GitHub (commit `abeeaf95`), while Claude Code's plugin is v1.3.1. Four skills differ by one sentence each: `grilling`, `code-review`, `research` and `codebase-design`. The other six are identical.
- `/setup-matt-pocock-skills` has not been run, so `code-review` has no issue tracker configured. Run it once if you need tracker-backed reviews.
