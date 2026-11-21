"""Booking ingest: pasted text, PDFs, screenshots or Gmail messages -> one Itinerary (Neon extracts, code merges)."""
import hashlib
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from google.genai import types

from overheard import config
from overheard.gemini import client, timed

KINDS = ["flight", "hotel", "train", "ticket"]

BOOKING_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": KINDS, "description": "ticket = museum, show or event entry"},
        "title": {"type": "string", "description": "short title, e.g. 'Air France AF 23, New York JFK to Paris CDG'"},
        "operator": {"type": "string", "description": "airline, rail company, hotel or venue name, as the booking writes it"},
        "number": {"type": "string", "description": "flight or train number, e.g. 'AF 23' or '9315'; empty for hotels and venues"},
        "ref": {"type": "string", "description": "booking reference, PNR or confirmation code, exactly as printed"},
        "start": {"type": "string", "description": "ISO 8601 local time with UTC offset, e.g. 2026-11-24T19:30-05:00 (departure, check-in, entry)"},
        "end": {"type": "string", "description": "ISO 8601 local time with UTC offset (arrival, check-out, exit); empty if unknown"},
        "from_place": {"type": "string", "description": "departure station/airport+terminal, or the hotel/venue address"},
        "to_place": {"type": "string", "description": "arrival station/airport+terminal; empty for hotels and venues"},
        "city": {"type": "string", "description": "city where the traveller is during this booking (arrival city for transport)"},
        "country": {"type": "string", "description": "ISO 3166-1 alpha-2 of that city"},
        "langs": {"type": "array", "items": {"type": "string"}, "description": "ISO 639-1 languages of announcements and signs the traveller will meet, e.g. ['fr','en']"},
        "details": {"type": "string", "description": "seat, coach, room, stops, nearest metro or tram, in one or two sentences"},
    },
    "required": ["kind", "title", "operator", "number", "ref", "start", "end", "from_place", "to_place",
                 "city", "country", "langs", "details"],
}

SCHEMA = {
    "type": "object",
    "properties": {
        "traveller": {"type": "string", "description": "passenger or guest name, empty if none"},
        "bookings": {"type": "array", "items": BOOKING_SCHEMA},
    },
    "required": ["traveller", "bookings"],
}

PROMPT = """You read travel booking confirmations (emails, PDFs, screenshots) for a travel assistant.
Return every booking the input confirms: flights, hotels, trains, and timed tickets (museums, shows).
Ignore marketing, upsells and anything not booked. A round trip or multi-leg booking gives one booking per leg.
Copy the booking reference exactly. Write times as ISO 8601 local time with the UTC offset of that place on that date
(Paris and Amsterdam in November are +01:00, New York is -05:00). If the input is not a booking, return no bookings.
Input:
"""


# ---- pure helpers (tested without network) ----

def norm_number(kind: str, number: str) -> str:
    """'AF023' -> 'AF 23', 'Eurostar 9315' -> '9315', hotels and venues -> ''."""
    n = (number or "").strip().upper()
    if kind in ("hotel", "ticket"):
        return ""
    if kind == "flight":
        m = re.search(r"\b([A-Z0-9]{2})\s*-?\s*0*(\d{1,4})\b", n)
        return f"{m.group(1)} {m.group(2)}" if m else n
    if kind == "train":
        m = re.search(r"\d{3,5}", n)
        return m.group(0) if m else n
    return n


def start_key(s: str) -> float:
    """Sort key for ISO start times with offsets; unparseable times go last."""
    try:
        return datetime.fromisoformat(s).timestamp()
    except (TypeError, ValueError):
        return float("inf")


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _ascii(s).lower()).strip("_")


def _dedupe_key(b: dict) -> tuple:
    ref = re.sub(r"\s+", "", (b.get("ref") or "")).upper()
    if ref:
        return ("ref", ref, b["kind"], b["number"])  # one PNR can cover two legs with different numbers
    return ("nk", b["kind"], b["number"] or _slug(b.get("operator", "")), (b.get("start") or "")[:10])


def _richer(a: dict, b: dict) -> dict:
    """Merge two sightings of the same booking: keep non-empty fields, prefer the longer text."""
    out = dict(a)
    for k, v in b.items():
        if k == "source":
            continue
        if isinstance(v, list):
            out[k] = list(dict.fromkeys((out.get(k) or []) + v))
        elif v and (not out.get(k) or (isinstance(v, str) and len(v) > len(out.get(k) or ""))):
            out[k] = v
    return out


def merge(sightings: list[tuple[dict, str]]) -> list[dict]:
    """[(raw booking, source)] -> deduped Bookings sorted by start, each with a unique id and its source."""
    seen: dict[tuple, dict] = {}
    for raw, source in sightings:
        b = {k: raw.get(k, [] if k == "langs" else "") for k in BOOKING_SCHEMA["properties"]}
        b["kind"] = b["kind"] if b["kind"] in KINDS else "ticket"
        b["number"] = norm_number(b["kind"], b["number"])
        b["ref"] = (b["ref"] or "").strip()
        b["country"] = (b["country"] or "").strip().upper()
        b["langs"] = [l.strip().lower() for l in b["langs"] if l and l.strip()]
        key = _dedupe_key(b)
        if key in seen:
            seen[key] = _richer(seen[key], b)
        else:
            b["source"] = source
            seen[key] = b
    out = sorted(seen.values(), key=lambda b: start_key(b["start"]))
    used: set[str] = set()
    for b in out:
        base = f"{b['kind']}_{_slug(b['number']) or _slug(b['city']) or 'x'}"
        bid, i = base, 2
        while bid in used:
            bid, i = f"{base}_{i}", i + 1
        used.add(bid)
        b["id"] = bid
    return [{"id": b.pop("id"), **b} for b in out]


# ---- Neon extraction ----

def _source_of(item) -> str:
    return "paste" if isinstance(item, str) else "upload"


def extract(item) -> dict:
    """One item (text, or (bytes, mime)) -> {traveller, bookings: [raw booking]} via Neon on low thinking."""
    if isinstance(item, str):
        parts, summary = [PROMPT + item], f"ingest text {item.strip().splitlines()[0][:60] if item.strip() else ''}"
    else:
        data, mime = item
        parts = [PROMPT + "(see the attached file)", types.Part.from_bytes(data=data, mime_type=mime)]
        summary = f"ingest {mime} {len(data)}B"
    r = timed(config.NEON, summary, client().models.generate_content,
              model=config.NEON, contents=parts,
              config=types.GenerateContentConfig(
                  response_mime_type="application/json", response_json_schema=SCHEMA,
                  thinking_config=types.ThinkingConfig(thinking_level=config.NEON_THINKING)))
    out = json.loads(r.text)
    out.setdefault("bookings", [])
    return out


def parse(items, source: str | None = None, home_lang: str = "English") -> dict:
    """Strings or (bytes, mime) pairs -> Itinerary. `source` overrides the per-item default (paste / upload)."""
    items = [items] if isinstance(items, (str, tuple)) else list(items)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(extract, items))
    sightings, travellers = [], []
    for item, res in zip(items, results):
        if res.get("traveller"):
            travellers.append(res["traveller"])
        for b in res["bookings"]:
            sightings.append((b, source or _source_of(item)))
    bookings = merge(sightings)
    digest = hashlib.sha1(json.dumps([b["ref"] or b["id"] for b in bookings]).encode()).hexdigest()[:8]
    return {"id": f"ingest-{digest}", "traveller": travellers[0] if travellers else "Traveller",
            "home_lang": home_lang, "bookings": bookings}


if __name__ == "__main__":
    import sys
    from pathlib import Path
    paths = sys.argv[1:]
    its = [Path(p).read_text() if p.endswith((".txt", ".eml", ".md")) else
           (Path(p).read_bytes(), "application/pdf" if p.endswith(".pdf") else "image/png") for p in paths]
    print(json.dumps(parse(its), indent=1, ensure_ascii=False))
