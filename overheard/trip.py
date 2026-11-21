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


def extract_trip(route_text: str | None = None, image: bytes | None = None, mime: str = "image/jpeg") -> dict:
    parts = [PROMPT + (route_text or "(see the ticket or screenshot image)")]
    if image:
        parts.append(types.Part.from_bytes(data=image, mime_type=mime))
    r = timed(config.NEON, f"trip extract {route_text or 'image'}", client().models.generate_content,
              model=config.NEON, contents=parts,
              config=types.GenerateContentConfig(
                  response_mime_type="application/json", response_json_schema=TRIP_SCHEMA,
                  thinking_config=types.ThinkingConfig(thinking_level=config.NEON_THINKING)))
    return json.loads(r.text)
