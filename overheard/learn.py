"""Learning from "not me": a dismissal makes Hydrogen write 3 to 5 `not` questions for that booking (a yes means the
input is NOT about the booking), stored per itinerary and applied at score time as s(b) x (1 - not(b)).
Guard: Hydrogen also writes a few true alerts for the booking, Decision 1 answers every candidate on them, and any
candidate that says yes to a true alert is dropped, so learning cannot silence the real thing."""
import json, re, time
from concurrent.futures import ThreadPoolExecutor
from google.genai import types
from overheard import config
from overheard.gemini import ROOT, client, log_call, timed

LEARNED_DIR = ROOT / "data" / "abroad" / "learned"
MAX_NEW = 5
LAST = {}          # the latest learn() run: keep examples and dropped candidates, for evals and the UI
GUARD_MAX = 0.3   # a candidate scoring above this on any true alert for the booking is dropped

PROMPT = """You tune a travel assistant that listens to station announcements, signs, departure boards and news, and
alerts a traveller only when an input affects one of their bookings. A separate model answers yes/no questions about
each input. The traveller just said this alert was NOT about their booking, so it was a false alert.

The booking:
{booking}

The input that was wrongly flagged:
{input}

The questions that fired most strongly on it (probability, question):
{hits}

Write between 5 and 7 candidate yes/no questions (each under 25 words) that a separate model will answer about a future
input. Each question must be answered YES for this input and NO for any real disruption notice on this booking.
A yes means "this input is not about the booking".
Rules:
- Find what makes this input miss the booking: the other direction, another platform or terminal, another train or
  flight number, another date, another station or section of the line, another city, or a change that only touches
  stops the traveller never uses.
- A real alert for the booking may mention the other direction, other stops or other platforms in passing (transfer
  advice, where to board instead, "trains in both directions"). Every question must stay NO for such an alert, so ask
  whether the disruption itself is limited to the other case, never whether the other case is merely mentioned.
- Phrase the questions generally enough to catch the same mistake on a similar future input, not only this exact text.
- Do not ask about dates in a way that needs arithmetic.
- Prefer plain words (direction names, platform, train or flight number) over spatial reasoning such as "away from X".
- Ids are short snake_case and unique.

Also write 3 keep_examples: short, realistic disruption notices (1 to 3 sentences, the same style and language as the
input) that DO affect this booking. At least one must mention the other direction, another platform or other stops in
passing, the way real notices do. Candidates that say yes to a keep example will be thrown away.
"""

SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "q": {"type": "string"}},
        "required": ["id", "q"]}},
        "keep_examples": {"type": "array", "items": {"type": "string"}}},
    "required": ["questions", "keep_examples"],
}


def _path(it_id: str):
    return LEARNED_DIR / f"{it_id}.json"


def load_learned(it_id: str) -> list[dict]:
    p = _path(it_id)
    return json.loads(p.read_text()) if p.exists() else []


def save_learned(it_id: str, qs: list[dict]) -> None:
    """Write the full list of learned questions for this itinerary."""
    LEARNED_DIR.mkdir(parents=True, exist_ok=True)
    _path(it_id).write_text(json.dumps(qs, indent=1, ensure_ascii=False))


def add_learned(it_id: str, new: list[dict]) -> list[dict]:
    """Append new questions, skipping ids already stored. Returns the ones actually added."""
    have = load_learned(it_id)
    ids = {q["id"] for q in have}
    added = [q for q in new if q["id"] not in ids]
    save_learned(it_id, have + added)
    return added


def not_score(p: dict, learned: list[dict], booking_id: str) -> float:
    """not(b) = max probability over b's learned questions, 0 when b has none (or none were answered)."""
    vals = [p[q["id"]] for q in learned if q["booking_id"] == booking_id and q["id"] in p]
    return max(vals, default=0)


def apply_not(s: float, not_p: float) -> float:
    return s * (1 - not_p)


def _input_text(event: dict) -> str:
    inp = event.get("input", {})
    parts = [inp.get("text"), inp.get("quote")]
    for k in ("alert", "receipt"):
        v = event.get(k) or {}
        parts += [v.get("change"), v.get("gist")]
    parts = [x for x in parts if x]
    return "\n".join(dict.fromkeys(parts)) or f"(a {inp.get('kind', 'media')} input with no transcript)"


def _ask_hydrogen(prompt: str) -> dict:
    r = timed(config.HYDROGEN, "learn not-questions", client().models.generate_content,
              model=config.HYDROGEN, contents=prompt,
              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                 response_json_schema=SCHEMA,
                                                 thinking_config=types.ThinkingConfig(thinking_level="low")))
    return json.loads(r.text)


def _check(qs: list[dict], examples: list[str]) -> list[dict]:
    """One Decision 1 call per keep example; returns [{question_id: p}] in example order."""
    questions = {q["id"]: {"type": "noul", "instructions": q["q"]} for q in qs}

    def one(i_ex):
        i, ex = i_ex
        t0 = time.time()
        r = client().decisions.create(model=config.DECISION, input=[{"type": "text", "text": ex}], questions=questions)
        log_call(config.DECISION, f"learn guard example {i} ({len(questions)} q)", time.time() - t0)
        return {k: r.answers[k].noul for k in questions if k in r.answers}

    with ThreadPoolExecutor(4) as ex:
        return list(ex.map(one, enumerate(examples)))


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "q"


def learn(dismissal: dict, event: dict, it: dict) -> list[dict]:
    """Dismissal -> up to 5 TaggedQuestions with group "not", tagged with the dismissed booking. Does not save.
    Each question carries guard_max: its highest probability on Hydrogen's true alerts for the booking."""
    bid = dismissal["booking_id"]
    booking = next((b for b in it["bookings"] if b["id"] == bid), None)
    if booking is None:
        raise KeyError(bid)
    hits = [h for h in (event.get("verdict") or {}).get("top_hits", []) if h.get("booking_id") in (None, bid)]
    prompt = PROMPT.format(
        booking=json.dumps(booking, ensure_ascii=False),
        input=_input_text(event) + (f"\nTraveller's note: {dismissal['note']}" if dismissal.get("note") else ""),
        hits="\n".join(f"{h['p']:.2f}  {h['q']}" for h in hits[:8]) or "(none recorded)")
    got = _ask_hydrogen(prompt)
    cands, seen = [], set()
    for raw in got["questions"]:
        base = f"not__{bid}__{_slug(raw['id'])}"
        qid, n = base, 2
        while qid in seen:
            qid, n = f"{base}_{n}", n + 1
        seen.add(qid)
        cands.append({"id": qid, "booking_id": bid, "group": "not", "q": raw["q"].strip()})
    examples = [e for e in got.get("keep_examples", []) if e.strip()]
    probs = _check(cands, examples) if examples and cands else []
    out, dropped = [], []
    for q in cands:
        g = max((p.get(q["id"], 0.0) for p in probs), default=0.0)
        if g <= GUARD_MAX:
            out.append(dict(q, guard_max=round(g, 3)))
        else:
            dropped.append(dict(q, guard_max=round(g, 3)))
    LAST.clear()
    LAST.update(keep_examples=examples, dropped=dropped, kept=out[:MAX_NEW])
    return out[:MAX_NEW]
