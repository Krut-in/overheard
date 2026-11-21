# Decisions API cheat sheet (`gemini-decision-1`)

It scores closed questions (yes/no, pick one, rubric) over one shared input in a single pass. It returns calibrated probabilities and no generated text, so your code can branch on a real number instead of a self-reported one.

## Call shape
- REST: `POST https://generativelanguage.googleapis.com/v1beta/decisions` with header `x-goog-api-key`.
- Python: `google-genai` 3.2 or later, `genai.Client(http_options={"api_version": "v1beta"})`, then `client.decisions.create(model, input, questions)`.
- `input`: a string, or a list of blocks of type `text`, `image`, `audio`, `video` or `document` (PDF). Each block takes base64 `data` or a `uri`, plus `mime_type`. Image and video blocks take `resolution` (`low` uses about 4x fewer tokens with the same answers).
- `questions`: 1 to 1,000 per request, each evaluated independently.

| Type | You send | You get back |
|---|---|---|
| `noul` | `instructions`, optional `criteria.true_description` and `criteria.false_description` | `noul` from 0.01 to 0.99, and `confidence` |
| `choice` | `criteria`: 2 to 255 options (key and description) | `choice`, `probabilities` (sum to 1), `confidence` |
| `score` | `criteria`: ordered levels, lowest first (2 to 10 recommended) | weighted `score`, `probabilities`, `legend`, `confidence` |

```python
from google import genai
client = genai.Client(http_options={"api_version": "v1beta"})
result = client.decisions.create(
    model="gemini-decision-1",
    input=[
        {"type": "text", "text": "Customer claim: mug arrived cracked.\nEvidence:\n"},
        {"type": "image", "uri": "https://storage.googleapis.com/generativeai-downloads/images/spill.jpg",
         "mime_type": "image/jpeg", "resolution": "low"},
    ],
    questions={
        "is_damaged": {"type": "noul", "instructions": "Does the photo show a damaged item?"},
        "queue": {"type": "choice", "instructions": "Which queue should handle this?",
                  "criteria": {"refund": "Refund requests.", "other": "Anything else."}},
    },
)
a = result.answers["is_damaged"]
print(a.noul, a.confidence, result.answers["queue"].choice)
```

## Gotchas
- `choice` keys are sorted alphabetically before scoring. Use an `other` key, not `none_of_the_above`.
- `noul` tops out at 0.99, so never test `> 0.99`.
- Do math and date comparisons in code, not in questions.
- No tools, history, caching, Batch, or Vertex AI.

## Limits
- Context: 262,144 tokens across input plus questions.
- Inline data up to 100 MB per request (50 MB for PDFs). External URLs up to 15 MB each. No YouTube or `gs://` links.
- Free tier: 200 requests per minute, 10,000 per day. Free-tier data may be used for training.
- Price: $0.10 per 1M input tokens, output free.
- Latency: Google claims 150 to 250 ms. Measured: about 325 ms for one question, 0.7 to 0.9 s per image, 1.5 to 2.2 s per video. It slows a lot past about 50 long questions.

## Calibration
- Google reports a top-1 calibration error of 0.025, against 0.21 for Flash-Lite. A DataCamp test kept 63% of answers at 95.6% accuracy with a 0.90 threshold.
- Thresholds in the codelab: auto-handle at 0.80 or higher. Tune on your own labeled data.

## Sources
https://aistudio.google.com/docs/decisions-api , https://blog.google/innovation-and-ai/technology/developers-tools/gemini-decisions-api/ , https://codelabs.developers.google.com/getting-started-with-gemini-decisions-api?hl=en , https://www.datacamp.com/tutorial/gemini-decisions-api , https://agentspulse.github.io/tutorials/gemini-decisions-api/ , https://dev.classmethod.jp/en/articles/gemini-decision-1-multimodal/ , https://aistudio.google.com/docs/rate-limits , https://aistudio.google.com/docs/pricing
