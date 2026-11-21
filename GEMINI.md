# Project context for Gemini CLI and Claude Code

This repo is our entry for the Gemini 4 NYC Hackathon (Cerebral Valley and Google DeepMind), on Saturday 2026-11-21. Submissions close at **5:00 PM ET**. The repo will be **public**.

Both coding agents read this file. Gemini CLI loads it directly, and Claude Code loads it through `CLAUDE.md`, which holds only `@GEMINI.md`. Edit this file, never `CLAUDE.md`, so the two tools keep one set of instructions.

## What we are building: Overheard
Overheard takes in what a traveller hears and sees at a station (announcements, posters, departure boards, short videos) and tells them only the part that affects their trip. It whispers the change in their language and shows their own photo with the relevant line circled and translated. Everything it ignores leaves a silence receipt with a relevance score.

The core is one trip fingerprint shared by every input. Neon extracts the trip and Hydrogen expands it into a few hundred yes/no questions. Then `gemini-decision-1` scores each input against those questions. `SCOPE.md` has the full plan, demo script, timeline and cut order. Treat `SCOPE.md` as read-only unless the user asks for a scope change.

## Hard rules
- Use at least two Gemini 4 models with distinct jobs, and ideally the Decisions API (`gemini-decision-1`). Model IDs and jobs are listed in `MODELS.md`.
- Never hardcode or print the API key. Read `GEMINI_API_KEY` from the environment (`.env` is gitignored). If a key ever lands in git history, Google disables it.
- Speed over polish. Build the core demo path first, then extend.
- **Update `PROGRESS.md` after each milestone and before you stop**, whichever tool you are. Fill in the current milestone, what got done and how long it took, the next step, decisions made, and known issues. The next agent may be the other tool, and it starts from that file.

## Where things are
- `SCOPE.md`: the Overheard plan (pitch, model pipeline, demo, proof, timeline, cut order)
- `PROGRESS.md`: live build state, the handoff point when switching between Gemini CLI and Claude Code
- `MODELS.md`: verified model IDs, each model's job, and the Neon speed tip
- `DECISIONS.md`: Decisions API (`gemini-decision-1`) call shape, question types, gotchas and limits
- `MANAGED_AGENTS.md`: Managed Agents (Interactions API, `antigravity-preview-09-2026`) for the ffmpeg highlight clip
- `IDEAS.md`: candidate project ideas scored against the judging rubric
- `RESEARCH.md`: event rules, judging criteria, and prize notes
- `SHOPIFY.md`: Shopify notes from the idea phase
- `GEMINI_MODEL_TESTS.md`: our own measurements of the Gemini 4 models and prompt variations
- The `geminiDocs` MCP server (`gemini_search_docs`, `gemini_get_doc`) gives live Gemini API docs. Check it before guessing an API shape.

## Skills
Skills live in `.agents/skills/` and are pinned in `skills-lock.json` (installed with `npx skills`). Gemini CLI loads them from there. Claude Code gets the same Matt Pocock skills from the `mattpocock-skills` plugin enabled in `.claude/settings.json`.

| Skill | Use it when |
|---|---|
| `gemini-api-dev` | writing any Gemini API call |
| `grilling` | stress-testing a plan before building |
| `prototype` | answering a design question with throwaway code |
| `tdd` | building a feature or fixing a bug test-first |
| `diagnosing-bugs` | something is broken or slow |
| `domain-modeling` | naming things, `GLOSSARY.md`, ADRs |
| `codebase-design` | deciding module interfaces and seams |
| `code-review` | reviewing the diff since a commit |
| `pr` | writing a PR body |
| `research` | gathering facts from primary sources into a Markdown file |
| `writing-for-agents` | editing this file, a skill, or any doc an agent reads |

Several of these skills read `GLOSSARY.md` and `docs/adr/` when they exist. Create them lazily, only when a term or decision is settled.

## Coding guidelines
- Use the `google-genai` SDK (Python) or `@google/genai` (JS). Do not use the old `google-generativeai` package.
- Put model names and other settings in one config file.
- Write one file per feature, and start each file with a short comment explaining what it does.
- Log every Gemini call with its model, prompt summary, and latency. This helps the "proof it works" part of judging.
- For calls a user waits on, set `thinkingConfig.thinkingLevel = "low"` on Neon. Its default thinking can take more than 60 s on long outputs.
- On 429 errors, raise the spend cap at aistudio.google.com/spend. On 503 errors, retry with backoff.
- Commit small and often, so we can roll back if a change breaks the demo. Never commit `.env`.

## Switching tools mid-build
1. Before you stop, update `PROGRESS.md` and commit.
2. The next tool starts by reading `PROGRESS.md`, then `git log --oneline -10`.
3. Gemini CLI uses `gemini-4-neon` by default (`.gemini/settings.json`). Claude Code uses its own model.
