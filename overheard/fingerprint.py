"""Trip -> fingerprint: a few hundred short yes/no questions written by Hydrogen, grouped so Decision 1 scores can be combined."""
import hashlib, json
from pathlib import Path
from google.genai import types
from overheard import config
from overheard.gemini import client, timed, ROOT

CACHE = ROOT / "data" / "fingerprints"
CACHE.mkdir(parents=True, exist_ok=True)

GROUPS = {
    "line": "mentions the rider's line (any spelling, any language)",
    "station": "mentions one of the rider's stations: board, alight, or a stop between (any spelling, any language)",
    "change": "says there is a disruption of a given type (delay, suspension, skipped stop, reroute, platform/track change, entrance closed, shuttle bus, express/local change), any language",
    "combo": "says a specific disruption affects the rider's line, direction, or stations (the high-signal questions)",
}

PROMPT = """You write the trip fingerprint for a subway assistant. A separate model will answer each question yes/no
about one announcement audio clip or one photo of a poster/countdown clock, in English or Spanish.

Trip: {trip}

Write between 220 and 320 short yes/no questions, each under 20 words, each about what the input SAYS or SHOWS.
Groups (use these exact group keys):
- line: {line}
- station: {station}
- change: {change}
- combo: {combo}
Rules:
- Cover English and Spanish phrasings, spoken forms ("seventy-second street", "calle 72"), abbreviations and line-bullet visuals.
- station questions must cover the boarding station, the alighting station and every stop between.
- combo questions must pair the rider's line and direction or stations with each disruption type. Write at least 80 combo questions.
- Do not ask about dates or times; do not ask questions whose answer needs arithmetic.
- Ids are short snake_case and unique.
"""

SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "group": {"type": "string", "enum": list(GROUPS)},
                       "q": {"type": "string"}},
        "required": ["id", "group", "q"]}}},
    "required": ["questions"],
}


def build_fingerprint(trip: dict) -> list[dict]:
    key = hashlib.sha1(json.dumps(trip, sort_keys=True).encode()).hexdigest()[:10]
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    r = timed(config.HYDROGEN, f"fingerprint {trip.get('summary','')}", client().models.generate_content,
              model=config.HYDROGEN,
              contents=PROMPT.format(trip=json.dumps(trip), **GROUPS),
              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                 response_json_schema=SCHEMA,
                                                 thinking_config=types.ThinkingConfig(thinking_level="low")))
    qs, seen = [], set()
    for q in json.loads(r.text)["questions"]:
        qid = q["id"]
        while qid in seen:
            qid += "_x"
        seen.add(qid)
        qs.append({**q, "id": qid})
    path.write_text(json.dumps(qs, indent=1, ensure_ascii=False))
    return qs
