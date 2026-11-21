"""Learning from "not me": a dismissal makes Hydrogen write 3 to 5 `not` questions for that booking (a yes means the
input is NOT about the booking), stored per itinerary and applied at score time as s(b) x (1 - not(b))."""
import json, re
from google.genai import types
from overheard import config
from overheard.gemini import ROOT, client, timed

LEARNED_DIR = ROOT / "data" / "abroad" / "learned"
MAX_NEW = 5

PROMPT = """You tune a travel assistant that listens to station announcements, signs, departure boards and news, and
alerts a traveller only when an input affects one of their bookings. A separate model answers yes/no questions about
each input. The traveller just said this alert was NOT about their booking, so it was a false alert.

The booking:
{booking}

The input that was wrongly flagged:
{input}

The questions that fired most strongly on it (probability, question):
{hits}

Write between 3 and 5 short yes/no questions (each under 25 words) that a separate model will answer about a future
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
- Ids are short snake_case and unique.
"""

SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "q": {"type": "string"}},
        "required": ["id", "q"]}}},
    "required": ["questions"],
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


def _ask_hydrogen(prompt: str) -> list[dict]:
    r = timed(config.HYDROGEN, "learn not-questions", client().models.generate_content,
              model=config.HYDROGEN, contents=prompt,
              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                 response_json_schema=SCHEMA,
                                                 thinking_config=types.ThinkingConfig(thinking_level="low")))
    return json.loads(r.text)["questions"]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "q"


def learn(dismissal: dict, event: dict, it: dict) -> list[dict]:
    """Dismissal -> 3 to 5 TaggedQuestions with group "not", tagged with the dismissed booking. Does not save."""
    bid = dismissal["booking_id"]
    booking = next((b for b in it["bookings"] if b["id"] == bid), None)
    if booking is None:
        raise KeyError(bid)
    hits = [h for h in (event.get("verdict") or {}).get("top_hits", []) if h.get("booking_id") in (None, bid)]
    prompt = PROMPT.format(
        booking=json.dumps(booking, ensure_ascii=False),
        input=_input_text(event) + (f"\nTraveller's note: {dismissal['note']}" if dismissal.get("note") else ""),
        hits="\n".join(f"{h['p']:.2f}  {h['q']}" for h in hits[:8]) or "(none recorded)")
    out, seen = [], set()
    for raw in _ask_hydrogen(prompt)[:MAX_NEW]:
        base = f"not__{bid}__{_slug(raw['id'])}"
        qid, n = base, 2
        while qid in seen:
            qid, n = f"{base}_{n}", n + 1
        seen.add(qid)
        out.append({"id": qid, "booking_id": bid, "group": "not", "q": raw["q"].strip()})
    return out
