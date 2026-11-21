"""Itinerary types, loading, and the itinerary fingerprint: Hydrogen writes 40 to 80 tagged yes/no questions per booking."""
import hashlib, json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal, NotRequired, TypedDict
from google.genai import types
from overheard import config
from overheard.gemini import client, timed, ROOT

CACHE = ROOT / "data" / "abroad" / "fingerprints"


class Booking(TypedDict):
    id: str
    kind: Literal["flight", "hotel", "train", "ticket"]
    title: str
    operator: str
    number: str
    ref: str
    start: str
    end: str
    from_place: str
    to_place: str
    city: str
    country: str
    langs: list[str]
    details: str
    source: Literal["gmail", "upload", "paste", "demo"]


class Itinerary(TypedDict):
    id: str
    traveller: str
    home_lang: str
    bookings: list[Booking]


class TaggedQuestion(TypedDict):
    id: str
    booking_id: str
    group: Literal["operator", "place", "change", "combo", "not"]
    q: str


Fingerprint = list[TaggedQuestion]


class Input(TypedDict):
    id: str
    kind: Literal["audio", "image", "video", "text", "news"]
    origin: Literal["mic", "upload", "radar", "rehearsal", "sample"]
    mime: NotRequired[str]
    data_b64: NotRequired[str]
    text: NotRequired[str]
    url: NotRequired[str]
    quote: NotRequired[str]
    published: NotRequired[str]
    dates: NotRequired[list[str]]
    lang: NotRequired[str]


class Hit(TypedDict):
    p: float
    q: str
    booking_id: str


class Verdict(TypedDict):
    input_id: str
    relevance: float
    booking_id: str | None
    per_booking: dict[str, float]
    change_type: str
    top_hits: list[Hit]
    route: Literal["alert", "carbon", "silence"]
    latency_s: float
    n_questions: int


GROUPS = {
    "operator": "mentions the booking's operator or service number (airline and flight number, train operator and "
                "train number, hotel name, museum name), any spelling, spoken forms included",
    "place": "mentions a place on the booking (airport and terminal, station, street, hotel or museum entrance, "
             "nearby metro or tram stop)",
    "change": "says there is a disruption of one type (strike, cancellation, delay, platform or track change, gate "
              "change, closure, schedule change), any language",
    "combo": "says a disruption hits this booking's operator, service number or place (the high-signal questions)",
}

PROMPT = """You write part of the itinerary fingerprint for a travel assistant. A separate model will answer each
question yes/no about one input: a station or airport announcement clip, a photo of a sign or departure board,
a short video, or a news article. Inputs can be in French, Dutch or English.

Whole itinerary (for context, so your questions do not also match the traveller's other bookings):
{others}

Write questions ONLY for this booking (booking_id "{bid}"):
{booking}

Write between {lo} and {hi} short yes/no questions, each under 18 words, each about what the input SAYS or SHOWS.
Groups (use these exact keys):
- operator: {operator}
- place: {place}
- change: {change}
- combo: {combo}
Rules:
- Phrase questions in English but name what the input would say in French, Dutch and English
  ("supprime", "annule", "greve", "geannuleerd", "staking", "vertraagd", "voie", "spoor", "porte").
- Cover spoken forms of numbers ("quatre-vingt-treize quinze", "AF vingt-trois"), abbreviations and codes.
- combo questions must pair this booking's operator AND service number, or its places, with each disruption type.
  At least a third of all questions are combo.
- Do not ask about dates or times; do not ask questions whose answer needs arithmetic.
- Ids are short snake_case and unique.
"""


def load(path: str | Path) -> Itinerary:
    return json.loads(Path(path).read_text())


def _schema(bid: str) -> dict:
    return {
        "type": "object",
        "properties": {"questions": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "booking_id": {"type": "string", "enum": [bid]},
                           "group": {"type": "string", "enum": list(GROUPS)}, "q": {"type": "string"}},
            "required": ["id", "booking_id", "group", "q"]}}},
        "required": ["questions"],
    }


def _summary(b: Booking) -> str:
    return f"{b['id']}: {b['title']} ({b['from_place']}{' to ' + b['to_place'] if b['to_place'] else ''})"


def _booking_questions(it: Itinerary, b: Booking) -> list[TaggedQuestion]:
    lo, hi = config.FP_PER_BOOKING
    keep = {k: b[k] for k in ("kind", "title", "operator", "number", "from_place", "to_place", "city", "details")}
    prompt = PROMPT.format(others="\n".join(_summary(x) for x in it["bookings"]), bid=b["id"],
                           booking=json.dumps(keep, ensure_ascii=False), lo=lo, hi=hi, **GROUPS)
    r = timed(config.HYDROGEN, f"abroad fingerprint {b['id']}", client().models.generate_content,
              model=config.HYDROGEN, contents=prompt,
              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                 response_json_schema=_schema(b["id"]),
                                                 thinking_config=types.ThinkingConfig(
                                                     thinking_level=config.FP_THINKING)))
    out = []
    for q in json.loads(r.text)["questions"][:hi]:
        if q.get("group") in GROUPS and q.get("q"):
            out.append({"id": f"{b['id']}__{q['id']}", "booking_id": b["id"], "group": q["group"], "q": q["q"]})
    return out


def itinerary_hash(it: Itinerary) -> str:
    return hashlib.sha1(json.dumps(it["bookings"], sort_keys=True).encode()).hexdigest()[:12]


def fingerprint(it: Itinerary) -> Fingerprint:
    """All bookings' tagged questions, one Hydrogen call per booking (3 at once), cached by itinerary hash."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{itinerary_hash(it)}.json"
    if path.exists():
        return json.loads(path.read_text())
    with ThreadPoolExecutor(config.FP_PARALLEL) as ex:
        per = list(ex.map(lambda b: _booking_questions(it, b), it["bookings"]))
    qs, seen = [], set()
    for q in (q for group in per for q in group):
        qid = q["id"]
        while qid in seen:
            qid += "_x"
        seen.add(qid)
        qs.append({**q, "id": qid})
    path.write_text(json.dumps(qs, indent=1, ensure_ascii=False))
    return qs


if __name__ == "__main__":
    import sys
    from collections import Counter
    it = load(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "abroad" / "itinerary.json")
    fp = fingerprint(it)
    print(len(fp), "questions", dict(Counter(q["booking_id"] for q in fp)), dict(Counter(q["group"] for q in fp)))
