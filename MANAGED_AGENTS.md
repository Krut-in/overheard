# Managed Agents cheat sheet

One Interactions API call hands Google a goal. Google runs the Antigravity agent loop (plan, act, observe) on its servers, and the loop works inside a Linux sandbox that Google hosts. Public preview since May 19, 2026.

- Agent: `antigravity-preview-09-2026`. Default model: `gemini-4-hydrogen`. Override with `agent_config.model` (`gemini-4-neon`, `gemini-4-carbon`, `gemini-4-argon`, and others).
- APIs: Interactions (`/v1beta/interactions`) runs things. Agents (`/v1beta/agents`) saves agent configs.

## Sandbox
- Ubuntu with Python 3.12 (numpy, pandas, requests, google-genai, bs4), Node 22, git, curl, jq, ripgrep, gcloud. The agent can install more with pip or npm.
- Network: open by default, or an `allowlist`, or `"network": "disabled"`. Secrets are injected by an egress proxy and never appear in the sandbox.
- Cold start up to about 5 s. Snapshotted after 15 min idle and resumed by ID. Deleted after 7 days of inactivity.
- Tools: `code_execution` (bash, Python, Node), `google_search`, `url_context`, file tools when an environment is set, your own `function` tools, and `mcp_server` tools (Streamable HTTP only, lowercase names).
- **Not available yet:** `computer_use`, `file_search`, `google_maps`. There is no browser tool.

## Calls
- `client.interactions.create(agent=..., input=..., environment="remote" | "env_..." | {config}, stream=True, background=True, previous_interaction_id=...)`
- Stream events: `interaction.created`, `step.start`, `step.delta`, `step.stop`, `interaction.completed`, `error`.
- Files in: mount `sources` (inline up to 1 MB, repository up to 500 MB, GCS up to 2 GB), or `PUT /upload/v1beta/environments/{id}/files/{path}`. Prompt input takes only text and base64 images.
- Files out: `GET /v1beta/environments/{id}/files/{path}?alt=media` (a single file, or a tar for a directory).
- Cancel: `client.interactions.cancel(id=...)`.

```python
from google import genai
client = genai.Client(http_options={"api_version": "v1beta"})
stream = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Write fib.py printing 20 Fibonacci numbers, run it, save output to out.txt",
    environment="remote",
    stream=True,
)
for ev in stream:
    if ev.event_type == "step.delta" and ev.delta.type == "text":
        print(ev.delta.text, end="", flush=True)
    elif ev.event_type == "interaction.completed":
        print("\nstatus:", ev.interaction.status)
```

## Self-hosted
1. `POST /v1beta/environments` with `{"mode": "self_hosted"}` returns `id` and a one-time `environment_key`.
2. Run `gemini-api environments connect --environment-key "$KEY" --root-dir /workspace` on your box. It needs outbound HTTPS only.
3. Pass the `id` as `environment`. The model and loop stay at Google, and only bash and file tools run on your machine.

## Cost and gotchas
- Standard token rates (Hydrogen $1.50 in and $7.50 out per 1M tokens). Sandbox compute is free in preview. Typical task: $0.25 to $3.25. Cap with `agent_config.max_total_tokens`.
- `temperature` returns a 400 error. No structured output.

## Sources
https://aistudio.google.com/docs/agents , https://aistudio.google.com/docs/antigravity-agent , https://aistudio.google.com/docs/agent-environment , https://aistudio.google.com/docs/streaming.md , https://aistudio.google.com/docs/pricing.md , https://github.com/google-gemini/gemini-api-cli/blob/main/docs/self-hosted/README.md , https://vercel.com/docs/sandbox/ecosystem/gemini-api
