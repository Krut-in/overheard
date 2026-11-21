"""Alerts, receipts, the Carbon band check and the daily digest for the abroad itinerary (SPEC.md, ticket F).

alert(inp, verdict, it, lang) -> Alert: Neon (thinking low) extracts the change and action for the hit booking,
Hydrogen translates, the subway `alert.whisper` voices it, and the proof is `alert.annotate` on the traveller's
photo, or the quoted line (plus source_url for news). Callers that want the text first pass `on_text`.
receipt(inp, verdict) -> Receipt: Hydrogen gist, `why` from the top hit question.
carbon_check(inp, verdict, it) -> {verdict: alert|silence, reason}: Carbon (thinking low) for the 0.4 to 0.8 band.
digest(events, it, today) -> Digest: pure; urgent = an alert whose booking starts within 48 hours of `today`.
"""
import base64, json, tempfile, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from google.genai import types

from overheard import alert as subway_alert
from overheard import config
from overheard.gemini import client, timed

MEDIA = Path(tempfile.gettempdir()) / "overheard_abroad_uploads"
LOW = types.ThinkingConfig(thinking_level="low")
_POOL = ThreadPoolExecutor(6)


def _parts(inp: dict) -> list:
    if inp.get("data_b64"):
        return [types.Part.from_bytes(data=base64.b64decode(inp["data_b64"]), mime_type=inp["mime"])]
    head = f"News item (published {inp.get('published', 'unknown')}, {inp.get('url', '')}):\n" \
        if inp.get("kind") == "news" else "Input text:\n"
    return [head + (inp.get("text") or inp.get("quote") or "")]


def _json(model: str, summary: str, contents: list, schema: dict) -> dict:
    r = timed(model, summary, client().models.generate_content, model=model, contents=contents,
              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                 response_json_schema=schema, thinking_config=LOW))
    return json.loads(r.text)


def booking_of(it: dict, booking_id: str | None) -> dict | None:
    return next((b for b in it.get("bookings", []) if b["id"] == booking_id), None)


def _booking_line(b: dict) -> str:
    return (f"{b['title']} ({b['kind']}, operator {b['operator']}, number {b.get('number') or 'none'}, "
            f"from {b.get('from_place') or b.get('city')} to {b.get('to_place') or b.get('city')}, "
            f"{b['start']} to {b['end']})")


CHANGE_SCHEMA = {"type": "object", "properties": {
    "quote": {"type": "string", "description": "the exact words in the input that state the change, in the input's "
                                               "language, as written or spoken"},
    "change": {"type": "string", "description": "one short English sentence: what changed for this booking"},
    "action": {"type": "string", "description": "one short English sentence: what the traveller should do now"},
    "source_language": {"type": "string"}},
    "required": ["quote", "change", "action", "source_language"]}


def extract_change(inp: dict, b: dict) -> dict:
    prompt = (f"A traveller abroad holds this booking: {_booking_line(b)}. This input (a station or airport "
              "announcement, a sign or board photo, or a news item) changes that booking. Extract the exact change and "
              "what the traveller should do. Name the service and time. Be concrete and short.")
    return _json(config.NEON, f"abroad change {inp['id']} for {b['id']}", [prompt, *_parts(inp)], CHANGE_SCHEMA)


def translate(change: dict, lang: str) -> dict:
    schema = {"type": "object", "properties": {
        "change": {"type": "string"}, "action": {"type": "string"},
        "whisper": {"type": "string", "description": "one or two calm sentences to whisper, combining change and action"}},
        "required": ["change", "action", "whisper"]}
    prompt = (f"Translate for a traveller into {lang}. Keep train and flight numbers, station, terminal and place names "
              f"as written. Input JSON: {json.dumps({'change': change['change'], 'action': change['action']})}")
    return _json(config.HYDROGEN, f"abroad translate to {lang}", [prompt], schema)


def _save(data: bytes, ext: str) -> str:
    MEDIA.mkdir(exist_ok=True)
    name = f"{uuid.uuid4().hex[:10]}{ext}"
    (MEDIA / name).write_bytes(data)
    return f"/api/abroad/media/{name}"


def _proof_text(inp: dict, quote: str) -> dict:
    if inp.get("kind") == "news":
        return {"kind": "quote", "url": inp.get("url"), "quote": inp.get("quote") or quote,
                "source_url": inp.get("url")}
    if inp.get("kind") in ("audio", "video"):
        return {"kind": "clip", "url": inp.get("url"), "quote": quote}
    return {"kind": "quote", "url": inp.get("url"), "quote": quote}


def alert(inp: dict, verdict: dict, it: dict, lang: str, on_text=None) -> dict:
    """Alert for the verdict's booking. `on_text(alert)` fires once change, action and translation are ready,
    before the whisper and the proof image (which take a few more seconds)."""
    b = booking_of(it, verdict["booking_id"])
    ch = extract_change(inp, b)
    tr = translate(ch, lang)
    a = {"input_id": inp["id"], "booking_id": b["id"], "change": ch["change"], "action": ch["action"],
         "quote": ch["quote"], "translated": {"change": tr["change"], "action": tr["action"], "lang": lang},
         "whisper_text": tr["whisper"], "whisper_url": None, "proof": _proof_text(inp, ch["quote"])}
    if on_text:
        on_text(a)
    voice = _POOL.submit(subway_alert.whisper, tr["whisper"])
    photo = None
    if inp.get("kind") == "image" and inp.get("data_b64"):
        photo = _POOL.submit(subway_alert.annotate, base64.b64decode(inp["data_b64"]), inp["mime"], ch["quote"],
                             tr["change"])
    try:
        a["whisper_url"] = _save(voice.result(timeout=40), ".wav")
    except Exception as e:  # noqa: BLE001
        a["whisper_error"] = str(e)[:160]
    if photo:
        try:
            img = photo.result(timeout=60)
            if img:
                a["proof"] = {"kind": "photo", "url": _save(img, ".png"), "quote": ch["quote"],
                              "original_url": inp.get("url")}
        except Exception as e:  # noqa: BLE001
            a["proof_error"] = str(e)[:160]
    return a


def _top_hit(verdict: dict) -> dict | None:
    hits = verdict.get("top_hits") or []
    bid = verdict.get("booking_id")
    return next((h for h in hits if h.get("booking_id") == bid), hits[0] if hits else None)


def why(verdict: dict) -> str:
    h = _top_hit(verdict)
    if not h:
        return f"no question fired (relevance {verdict.get('relevance', 0):.2f})"
    return f"top hit {h['p']:.2f}: {h['q']}"


def gist(inp: dict) -> str:
    r = timed(config.HYDROGEN, f"abroad gist {inp['id']}", client().models.generate_content, model=config.HYDROGEN,
              contents=["In at most 8 English words, say what this announcement, sign or news item is about, e.g. "
                        "'TER delay at Lyon Part-Dieu' or 'Schiphol Christmas crowds warning'. No period.",
                        *_parts(inp)],
              config=types.GenerateContentConfig(thinking_config=LOW))
    return (r.text or "").strip()


def receipt(inp: dict, verdict: dict, carbon: dict | None = None) -> dict:
    try:
        g = gist(inp)
    except Exception:  # noqa: BLE001
        g = inp.get("title") or inp.get("name") or inp.get("kind", "input")
    r = {"input_id": inp["id"], "gist": g, "relevance": verdict.get("relevance", 0.0),
         "nearest_booking_id": verdict.get("booking_id"), "why": why(verdict)}
    if carbon:
        r["carbon"] = carbon
        r["why"] = f"Carbon: {carbon['reason']} ({r['why']})"
    return r


CARBON_SCHEMA = {"type": "object", "properties": {
    "verdict": {"type": "string", "enum": ["alert", "silence"]},
    "reason": {"type": "string", "description": "one short sentence"}}, "required": ["verdict", "reason"]}


def carbon_check(inp: dict, verdict: dict, it: dict) -> dict:
    """0.4 to 0.8: Carbon reads the input and the booking and decides."""
    b = booking_of(it, verdict["booking_id"])
    hits = [{"p": round(h["p"], 2), "q": h["q"]} for h in (verdict.get("top_hits") or [])[:4]]
    prompt = (f"Booking: {_booking_line(b)}. A fast relevance model was unsure about this input "
              f"(relevance {verdict['relevance']:.2f}, strongest signals {json.dumps(hits, ensure_ascii=False)}). "
              "Answer 'alert' only when the input announces a change (cancellation, delay, strike, closure, gate, "
              "terminal, platform, entrance or schedule change) that hits THIS booking: its own service number, its "
              "stations, terminal or venue, on its dates. Another train or flight number, the other direction, another "
              "terminal, another date, or normal service is 'silence'.")
    return _json(config.CARBON, f"abroad band {inp['id']} {b['id']}", [prompt, *_parts(inp)], CARBON_SCHEMA)


def _start_day(b: dict) -> date:
    return datetime.fromisoformat(b["start"]).date()


def _end_day(b: dict) -> date:
    return datetime.fromisoformat(b["end"]).date()


def digest(events: list[dict], it: dict, today: str | date) -> dict:
    """Urgent: alerts whose booking starts between today and 48 hours later. Today: other alerts on bookings that
    are active today. Silent count and a sample of receipts."""
    day = date.fromisoformat(today) if isinstance(today, str) else today
    by_id = {b["id"]: b for b in it.get("bookings", [])}
    urgent, today_evs, receipts = [], [], []
    for ev in events:
        if ev.get("receipt"):
            receipts.append(ev["receipt"])
        if ev.get("status") != "alert":
            continue
        b = by_id.get((ev.get("alert") or {}).get("booking_id") or (ev.get("verdict") or {}).get("booking_id"))
        if not b:
            continue
        if timedelta(0) <= _start_day(b) - day <= timedelta(days=2):
            urgent.append(ev)
        elif _start_day(b) <= day <= _end_day(b):
            today_evs.append(ev)
    silent = sum(1 for e in events if e.get("status") == "silent")
    return {"date": day.isoformat(), "itinerary_id": it.get("id"), "urgent": urgent, "today": today_evs,
            "silent_count": silent, "receipts_sample": receipts[:5]}
