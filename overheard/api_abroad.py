"""The /api/abroad router: every route in the SPEC.md API table, talking to the phone page in web/abroad/.

Fixture mode (env OVERHEARD_FIXTURE=1) answers from web/abroad/fixture_feed.json and the fixture itinerary,
so the page works before the engine tickets land. Each route calls one `_engine_*` function; ticket F swaps
those bodies for the real engine (itinerary, match, ingest, gmail, radar, rehearsal, learn, abroad_alert).
"""
import copy, json, os, re, tempfile, threading, time, uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parent.parent
ITINERARY_PATH = ROOT / "data" / "abroad" / "itinerary.json"
FIXTURE_FEED = ROOT / "web" / "abroad" / "fixture_feed.json"
UPLOADS = Path(tempfile.gettempdir()) / "overheard_abroad_uploads"
MEDIA_DIRS = [ROOT / "web" / "abroad" / "media", UPLOADS, ROOT / "data" / "abroad" / "media",
              ROOT / "data" / "abroad" / "rehearsal"]
MIME_KIND = {"audio": "audio", "image": "image", "video": "video", "text": "text"}

router = APIRouter(prefix="/api/abroad")
STATE = {"itinerary": None, "n_questions": 0, "lang": "Hindi", "events": [], "learned": []}
LOCK = threading.Lock()


class EngineMissing(Exception):
    """Raised by an `_engine_*` function when fixture mode is off and ticket F has not wired the engine yet."""


def fixture_mode() -> bool:
    return os.environ.get("OVERHEARD_FIXTURE", "") not in ("", "0", "false")


def _fixture() -> dict:
    return json.loads(FIXTURE_FEED.read_text())


def _fixture_itinerary() -> dict:
    it = json.loads(ITINERARY_PATH.read_text())
    it.pop("note", None)
    return it


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


def _push(ev: dict) -> dict:
    with LOCK:
        STATE["events"].insert(0, ev)
    return ev


def _find(event_id: str) -> dict | None:
    return next((e for e in STATE["events"] if e["id"] == event_id), None)


def _play_later(items: list[dict], gap_s: float = 0.9):
    """Fixture playback: each item shows as `scoring` now and resolves to its final status a moment later."""
    for i, item in enumerate(items):
        final = copy.deepcopy(item)
        eid = _new_id(final["id"])
        iid = _new_id(final["input"]["id"])
        final.update(id=eid, t=_now_iso())
        final["input"]["id"] = iid
        for key in ("verdict", "receipt", "alert"):
            if key in final:
                final[key]["input_id"] = iid
        pending = {"id": eid, "t": final["t"], "status": "scoring", "input": final["input"]}
        _push(pending)

        def resolve(pending=pending, final=final):
            with LOCK:
                pending.clear()
                pending.update(final)
        threading.Timer(1.2 + gap_s * i, resolve).start()


# ---- engine seams: one per route; ticket F replaces the bodies ---------------------------------

def _engine_demo() -> tuple[dict, int, list[dict]]:
    if not fixture_mode():
        raise EngineMissing("itinerary.load + itinerary.fingerprint")
    fx = _fixture()
    return _fixture_itinerary(), fx["n_questions"], copy.deepcopy(fx["events"])


def _engine_ingest(texts: list[str], files: list[tuple[str, bytes, str]]) -> tuple[dict, int]:
    if not fixture_mode():
        raise EngineMissing("ingest.parse")
    return _fixture_itinerary(), _fixture()["n_questions"]


def _engine_gmail() -> tuple[dict, int]:
    if not fixture_mode():
        raise EngineMissing("gmail.fetch_booking_emails + ingest.parse")
    return _fixture_itinerary(), _fixture()["n_questions"]


def _engine_score(ev: dict, data: bytes, mime: str):
    """Fills `ev` in place: verdict plus receipt or alert, then a final status."""
    if not fixture_mode():
        raise EngineMissing("match.score + abroad_alert.alert/receipt")
    time.sleep(1.5)
    it = STATE["itinerary"] or {"bookings": [{"id": None}]}
    nearest = it["bookings"][0]["id"]
    iid = ev["input"]["id"]
    verdict = {"input_id": iid, "relevance": 0.0, "booking_id": nearest,
               "per_booking": {b["id"]: 0.0 for b in it["bookings"]}, "change_type": "none",
               "top_hits": [], "route": "silence", "latency_s": 1.5, "n_questions": STATE["n_questions"]}
    receipt = {"input_id": iid, "gist": f"{ev['input'].get('name', 'upload')} (fixture mode, not scored)",
               "relevance": 0.0, "nearest_booking_id": nearest,
               "why": "fixture mode: the live engine arrives with ticket F"}
    with LOCK:
        ev.update(status="silent", verdict=verdict, receipt=receipt)


def _engine_radar(today: str) -> list[dict]:
    if not fixture_mode():
        raise EngineMissing("radar.sweep + match.score")
    return _fixture()["radar"]


def _engine_rehearse(booking_id: str | None) -> list[dict]:
    if not fixture_mode():
        raise EngineMissing("rehearsal.rehearse + match.score")
    items = _fixture()["rehearsal"]
    if booking_id:
        items = [i for i in items if i["verdict"]["booking_id"] == booking_id] or items
    return items


def _engine_learn(ev: dict, booking_id: str, note: str) -> list[dict]:
    if not fixture_mode():
        raise EngineMissing("learn.learn + learn.save_learned")
    it = STATE["itinerary"] or _fixture_itinerary()
    b = next((x for x in it["bookings"] if x["id"] == booking_id), it["bookings"][0])
    day = b["start"][:10]
    qs = [f"Does it name a service other than {b['operator']} {b['number']}".strip() + "?",
          f"Is it about a date other than {day}?",
          f"Is it about a place other than {b['from_place'] or b['city']}?"]
    if ev.get("input", {}).get("quote"):
        qs.append(f"Is it the same kind of notice as \"{ev['input']['quote'][:60]}\" but for another booking?")
    return [{"id": f"not__{booking_id}__{uuid.uuid4().hex[:4]}", "booking_id": booking_id, "group": "not", "q": q}
            for q in qs]


def _engine_digest(today: str) -> dict:
    if not fixture_mode():
        raise EngineMissing("abroad_alert.digest")
    it = STATE["itinerary"] or {"id": None, "bookings": []}
    starts = {b["id"]: datetime.fromisoformat(b["start"]).date() for b in it["bookings"]}
    day = date.fromisoformat(today)
    urgent, today_evs, receipts = [], [], []
    for ev in STATE["events"]:
        v = ev.get("verdict") or {}
        b = v.get("booking_id")
        if ev["status"] == "alert" and v.get("relevance", 0) >= 0.8 and b in starts \
                and timedelta(0) <= starts[b] - day <= timedelta(days=2):
            urgent.append(ev)
        elif str(ev.get("t", ""))[:10] == today:
            today_evs.append(ev)
        if ev.get("receipt"):
            receipts.append(ev["receipt"])
    silent = sum(1 for e in STATE["events"] if e["status"] == "silent")
    return {"date": today, "itinerary_id": it["id"], "urgent": urgent, "today": today_evs,
            "silent_count": silent, "receipts_sample": receipts[:5]}


# ---- routes -------------------------------------------------------------------------------------

def _missing(e: EngineMissing) -> JSONResponse:
    return JSONResponse({"error": f"engine not wired yet ({e}); run with OVERHEARD_FIXTURE=1"}, status_code=503)


def _set_itinerary(it: dict, n: int, events: list[dict] | None = None) -> dict:
    with LOCK:
        STATE.update(itinerary=it, n_questions=n, events=events or [], learned=[])
    return {**it, "n_questions": n}


@router.post("/itinerary/demo")
async def itinerary_demo():
    try:
        it, n, events = _engine_demo()
    except EngineMissing as e:
        return _missing(e)
    return _set_itinerary(it, n, events)


@router.post("/itinerary/ingest")
async def itinerary_ingest(files: list[UploadFile] | None = File(None), text: str = Form("")):
    blobs = [(f.filename or "file", await f.read(), f.content_type or "") for f in files or []]
    try:
        it, n = _engine_ingest([text] if text else [], blobs)
    except EngineMissing as e:
        return _missing(e)
    return _set_itinerary(it, n)


@router.post("/itinerary/gmail")
async def itinerary_gmail():
    try:
        it, n = _engine_gmail()
    except EngineMissing as e:
        return _missing(e)
    return _set_itinerary(it, n)


@router.get("/itinerary")
async def itinerary_get():
    if not STATE["itinerary"]:
        return JSONResponse({"error": "no itinerary yet"}, status_code=404)
    return {**STATE["itinerary"], "n_questions": STATE["n_questions"]}


@router.post("/lang")
async def set_lang(lang: str = Form(...)):
    STATE["lang"] = lang
    return {"lang": lang}


@router.post("/input")
async def add_input(file: UploadFile = File(...)):
    data = await file.read()
    mime = file.content_type or "application/octet-stream"
    name = Path(file.filename or "input").name
    iid = _new_id("in")
    UPLOADS.mkdir(exist_ok=True)
    stored = f"{iid}{Path(name).suffix.lower()[:6]}"
    (UPLOADS / stored).write_bytes(data)
    inp = {"id": iid, "kind": MIME_KIND.get(mime.split("/")[0], "text"), "origin": "upload", "mime": mime,
           "url": f"/api/abroad/media/{stored}", "name": name}
    if name.startswith("mic_"):
        inp["origin"] = "mic"
    ev = _push({"id": _new_id("ev"), "t": _now_iso(), "status": "scoring", "input": inp})

    def run():
        try:
            _engine_score(ev, data, mime)
        except EngineMissing as e:
            with LOCK:
                ev.update(status="silent", receipt={"input_id": iid, "gist": name, "relevance": 0.0,
                                                    "nearest_booking_id": None, "why": str(e)})
        except Exception as e:  # noqa: BLE001
            with LOCK:
                ev.update(status="silent", error=str(e)[:200])
    threading.Thread(target=run, daemon=True).start()
    return ev


@router.get("/feed")
async def feed():
    it = STATE["itinerary"]
    with LOCK:
        events = copy.deepcopy(STATE["events"][:60])
    return {"itinerary_id": it["id"] if it else None, "lang": STATE["lang"], "fixture": fixture_mode(),
            "events": events}


@router.post("/radar")
async def radar(today: str = Form("")):
    try:
        items = _engine_radar(today or date.today().isoformat())
    except EngineMissing as e:
        return _missing(e)
    _play_later(items)
    return {"n_items": len(items)}


@router.post("/rehearse")
async def rehearse(booking_id: str = Form("")):
    try:
        items = _engine_rehearse(booking_id or None)
    except EngineMissing as e:
        return _missing(e)
    _play_later(items)
    return {"n_items": len(items)}


@router.post("/dismiss")
async def dismiss(event_id: str = Form(...), booking_id: str = Form(...), note: str = Form("")):
    ev = _find(event_id)
    if not ev:
        return JSONResponse({"error": f"no event {event_id}"}, status_code=404)
    try:
        added = _engine_learn(ev, booking_id, note)
    except EngineMissing as e:
        return _missing(e)
    with LOCK:
        ev["status"] = "dismissed"
        STATE["learned"].extend(added)
    return {"added": added}


@router.get("/digest")
async def digest(today: str = ""):
    try:
        return _engine_digest(today or date.today().isoformat())
    except EngineMissing as e:
        return _missing(e)


@router.get("/media/{name}")
async def media(name: str):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name.startswith("."):
        return JSONResponse({"error": "bad name"}, status_code=400)
    for d in MEDIA_DIRS:
        p = d / name
        if p.is_file():
            return FileResponse(p, media_type="audio/mp4" if p.suffix == ".m4a" else None)
    return JSONResponse({"error": "not found"}, status_code=404)
