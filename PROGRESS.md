# Progress

Every agent (Gemini CLI or Claude Code) updates this file after each milestone and before stopping. Newest entries go at the top of each section. Times are ET.

## Current milestone
Build session in progress on the `SCOPE.md` timeline. The build agent replaces this line with its real milestone.

## Done (with time)
- 2:15 PM: Tooling set up so both agents can build and hand off. Matt Pocock skills installed for both tools, `GEMINI.md` shared through `CLAUDE.md`, git initialised with a first commit, Gemini CLI checks passed (`GEMINI_MODEL_TESTS.md`). About 20 min. (Claude Code)

## Next step
Whoever picks this up: read `SCOPE.md`, check `git log --oneline -10`, and record here what the build session has finished so far.

## Decisions made
- One instructions file: `GEMINI.md`. `CLAUDE.md` only imports it.
- Skills for Gemini CLI live in `.agents/skills/` and are pinned in `skills-lock.json`. Claude Code gets the same skills from the `mattpocock-skills` plugin.

## Known issues
- The `.agents/skills/` copies come from `mattpocock/skills` on GitHub (commit `abeeaf95`), while Claude Code's plugin is v1.3.1. Four skills differ by one sentence each: `grilling`, `code-review`, `research` and `codebase-design`. The other six are identical.
- `/setup-matt-pocock-skills` has not been run, so `code-review` has no issue tracker configured. Run it once if you need tracker-backed reviews.
