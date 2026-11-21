# Models available on our hackathon key

Verified on 2026-11-21 by listing `GET https://generativelanguage.googleapis.com/v1beta/models` with the key in `.env` (project `gemini4nyc26nyc-2198`, Tier 3).

| Model ID | Context in / max out | Job in this project |
|---|---|---|
| `gemini-4-hydrogen` | 1M / 65K tokens | Cheapest and fastest. Use it for high-volume or repetitive steps and as a fast sub-agent. |
| `gemini-4-argon` | 1M / 32K tokens | General-purpose default. Use it for document synthesis, everyday app logic, and lower cost per turn than Carbon. |
| `gemini-4-neon` | 1M / 65K tokens | Strong at coding, writing, and research workflows, with reasoning near Carbon's level. It is our pick for the coding agent (Gemini CLI). |
| `gemini-4-carbon` | 1M / 32K tokens | Strongest model, for the hardest reasoning and long-horizon agent work. It is the slowest and costliest, so use it sparingly. |
| `gemini-decision-1` | 262K in, typed output | Decisions API (`createDecision`). It scores up to 1,000 yes/no, multiple-choice, or 1-to-N scale questions per request and returns calibrated probabilities. It does not support `generateContent`. |

All four Gemini 4 models support `generateContent`, `countTokens`, `batchGenerateContent`, and thinking.

## Neon speed tip (measured 2026-11-21)

Neon thinks hard by default. For a 400-word pitch it spent 9,811 thinking tokens and took 77 s before showing any text. Adding `"generationConfig": {"thinkingConfig": {"thinkingLevel": "low"}}` cut that to 14 s to first text and 18 s in total, with the same quality. Use `low` for user-facing and creative calls, and keep the default for hard reasoning and code.

## Quick test

```bash
set -a; . ./.env; set +a
curl -s -H "x-goog-api-key: $GEMINI_API_KEY" -H 'Content-Type: application/json' \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-4-neon:generateContent" \
  -d '{"contents":[{"parts":[{"text":"Hello"}]}]}'
```

Decisions API from Python (SDK form per community examples, so confirm against the official docs): `client.decisions.create(model="gemini-decision-1", ...)` with the client created as `genai.Client(http_options={"api_version": "v1beta"})`.

## Other models on the key worth knowing

- `gemma-4-31b-it`, `gemma-4-26b-a4b-it`: open Gemma 4 models
- `deep-research-preview-04-2026`, `deep-research-max-preview-04-2026`: Deep Research agents
- `genie-4`: real-time audio and video generation (bidi streaming only)

The job notes come from Google's Decisions API launch post and from third-party comparison guides. Google has no single official model-picker page yet.
