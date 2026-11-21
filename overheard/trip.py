"""Ticket photo or spoken/typed route -> structured trip, using Neon on low thinking."""
import json
from google.genai import types
from overheard import config
from overheard.gemini import client, timed

TRIP_SCHEMA = {
    "type": "object",
    "properties": {
        "system": {"type": "string"},
        "line": {"type": "string", "description": "subway line letter or number, e.g. Q"},
        "other_lines": {"type": "array", "items": {"type": "string"}, "description": "transfer lines, if any"},
        "direction": {"type": "string", "description": "e.g. northbound / Manhattan-bound / Flushing-bound"},
        "board": {"type": "string"},
        "alight": {"type": "string"},
        "stops_between": {"type": "array", "items": {"type": "string"}, "description": "every station between board and alight on this line, in order"},
        "when": {"type": "string", "description": "date/time if known, else 'today'"},
        "summary": {"type": "string", "description": "one sentence, e.g. 'Q train northbound from Times Sq-42 St to 72 St'"},
    },
    "required": ["system", "line", "direction", "board", "alight", "stops_between", "summary"],
}

PROMPT = """You extract a New York City subway trip for a travel assistant.
Return the trip as JSON. Use official MTA station names (e.g. "Times Sq-42 St", "72 St", "Jay St-MetroTech").
Fill stops_between with every station the train stops at strictly between board and alight, in order, from your knowledge of the line.
If the direction is not stated, infer it from board and alight (e.g. Manhattan-bound, Flushing-bound, uptown, northbound).
Input: """


_CACHE = {}


def extract_trip(route_text: str | None = None, image: bytes | None = None, mime: str = "image/jpeg") -> dict:
    """Typed routes are cached so the same route always maps to the same trip (and the same cached fingerprint)."""
    import hashlib, pathlib
    key = (route_text or "").strip().lower() if not image else hashlib.sha1(image).hexdigest()
    cache = pathlib.Path(__file__).resolve().parent.parent / "data" / "fingerprints" / "routes.json"
    if not _CACHE and cache.exists():
        _CACHE.update(json.loads(cache.read_text()))
    if key and key in _CACHE:
        return _CACHE[key]
    trip = _extract(route_text, image, mime)
    if key:
        _CACHE[key] = trip
        cache.write_text(json.dumps(_CACHE, indent=1))
    return trip


def _extract(route_text, image, mime) -> dict:
    parts = [PROMPT + (route_text or "(see the attached ticket photo, screenshot, or spoken route recording)")]
    if image:
        parts.append(types.Part.from_bytes(data=image, mime_type=mime))
    r = timed(config.NEON, f"trip extract {route_text or 'image'}", client().models.generate_content,
              model=config.NEON, contents=parts,
              config=types.GenerateContentConfig(
                  response_mime_type="application/json", response_json_schema=TRIP_SCHEMA,
                  thinking_config=types.ThinkingConfig(thinking_level=config.NEON_THINKING)))
    return json.loads(r.text)
