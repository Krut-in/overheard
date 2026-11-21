# Gemini 4 capability sheet (researched 2026-11-21)

Primary source: the AI Studio changelog and model pages. Third-party blogs were used only for speed and benchmark color, and they disagree on some numbers.

## Gemini 4 text models (all GA)

All four share a 1,048,576-token context, take text, image, video, audio and PDF as input, and output text only. None of them supports the Live API, image generation or audio generation. All support function calling, structured outputs, code execution, computer use, Google Search and Maps grounding, File Search, URL context and agentic video understanding.

| Model ID | Job in a build | Thinking levels | Price per 1M tokens (in / out) |
|---|---|---|---|
| `gemini-4-hydrogen` | Fast, cheap worker: per-frame or per-item loops, sub-agents. Default model of the Antigravity managed agent. Free tier available. | low, medium, high (default), xhigh | $1.50 / $7.50 |
| `gemini-4-neon` | Fast frontier model (released Nov 18): planner, long-video reasoning, coding agent. Blogs report it matches Carbon on intelligence at about twice the speed. Also reads Word, PowerPoint and Excel, and can slice video by time interval. | low, medium, high (default), xhigh | $3.00 / $15.00 |
| `gemini-4-carbon` | Hardest reasoning: final judge or verifier where a mistake costs the most. Blogs say it has a lower hallucination rate than Neon. | low, medium, high | $2.00 / $10.00 (intro price until Nov 30) |
| `gemini-4-argon` | October model, efficient reasoning. Mostly superseded by Neon and Hydrogen. Use only as a fallback. | low, medium, high | not stated |

## Decisions API (Nov 11)

- Model `gemini-decision-1`. It scores options you supply and does not generate text.
- Question types: `noul` (yes/no probability, 0.01 to 0.99), `choice` (pick 1 of 2 to 255 options), `score` (rubric with 2 to 255 ordered levels).
- Up to 1,000 questions over one shared multimodal input (image, audio, video, PDF).
- Speed: 50 to 100 ms model compute, 150 to 250 ms end to end. Price: $0.10 per 1M input tokens, output is free.
- Common pattern: confidence of 0.7 or higher runs automatically, 0.4 to 0.7 goes to a bigger model, and below 0.4 goes to a human.
- No Batch API, context caching or Flex and Priority inference.

## Managed Agents

- Antigravity agent `antigravity-preview-09-2026`, which now runs on Hydrogen by default. Each interaction gets a full Linux sandbox from one API call.
- Google-hosted sandbox (free) or self-hosted: create an environment with mode `self_hosted`, then run `gemini-api environments connect` inside your own box. It needs outbound HTTPS only. Guides cover Docker, local mode, Cloud Run, Modal, E2B, Daytona, Fly.io, Cloudflare and Vercel Sandbox.
- Gemini API CLI `gemini-api` (beta since Oct 27) can run managed agents.
- Deep Research agents: `deep-research-preview-04-2026` and `deep-research-max-preview-04-2026`.
- Computer Use tool is GA (Oct 30) on the Interactions and GenerateContent APIs.

## Media models

| Model ID | What it does |
|---|---|
| `gemini-3.8-live`, `gemini-3.8-live-extended-thinking` | Live API for real-time voice and camera. These are not Gemini 4, so a Live build still needs two Gemini 4 models elsewhere. |
| `gemini-3.5-transcribe`, `gemini-3.5-transcribe-live` | Transcription with voice-driven editing (Nov 17). |
| `gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts` | Speech generation with voice remixing and stored voice IDs (Nov 4). |
| `gemini-nano-banana-2.1` | Image generation and editing at 1K, 2K and 4K (Oct 6). |
| `gemini-omni-1.2-flash` | Video generation up to 15 s, extendable to 30 s, with conversational edits and up to 6 reference images (Nov 5). $12 per 1M video tokens. |
| `lyria-3.5` | Music generation, 44.1 kHz stereo (Sept 3). |
| `genie-4` | Interactive world generation: streams steerable 24 fps video with audio over WebRTC (Nov 19). About $0.10 per second. |

Also new: multimodal function responses that can return audio, video and Office files (Nov 5), and Tool retrieval in preview (Nov 19).

## Shopify bonus (shop.dev)

- Shop MCP at `https://mcp.shop.com` connects to Shopify Catalog, Shop sign-in, cart, checkout and Shop Pay.
- Global Catalog searches every Shopify merchant: `catalog.shopify.com/api/ucp/mcp` (API key, no approval needed).
- Storefront Catalog for one store: `{storeDomain}/api/ucp/mcp` (no key). Tools: `search_catalog`, `lookup_catalog`, `get_product`, plus a separate Cart MCP.
- The old Storefront MCP at `/api/mcp` is retired. Use UCP.

## Sources

- AI Studio changelog: https://aistudio.google.com/docs/changelog
- Model pages: https://aistudio.google.com/docs/models/gemini-4-neon , https://aistudio.google.com/docs/models/gemini-4-hydrogen , https://aistudio.google.com/docs/models/gemini-4-carbon , https://aistudio.google.com/docs/models/gemini-4-argon
- Decisions API: https://aistudio.google.com/docs/decisions-api , https://www.marktechpost.com/2026/11/11/google-gemini-decisions-api-gemini-decision-1/ , https://codelabs.developers.google.com/getting-started-with-gemini-decisions-api?hl=en
- Managed Agents: https://blog.google/innovation-and-ai/technology/developers-tools/managed-agents-gemini-api/ , https://ai.google.dev/gemini-api/docs/agents , https://github.com/google-gemini/gemini-api-cli/tree/main/docs/self-hosted
- Model comparisons (third party): https://www.valyu.ai/blogs/gemini-4-neon-vs-carbon-vs-hydrogen-vs-argon , https://pasqualepillitteri.it/en/news/32764/which-gemini-4-argon-carbon-hydrogen-compared
- Shopify: https://www.shopify.com/news/fall-26-edition-developer , https://shopify.dev/docs/agents/catalog , https://shopify.dev/changelog/add-shopping-and-shop-pay-checkout-to-any-agent-with-shop-mcp
