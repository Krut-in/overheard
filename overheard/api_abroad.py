"""The /api/abroad router: every route in the SPEC.md API table, talking to the phone page in web/abroad/.

Real mode (default): each route calls one `_engine_*` function backed by the engine (itinerary, match, ingest,
gmail, radar, rehearsal, learn, abroad_alert). Inputs score in a pool of 3 (at most 3 Decision calls at once); the
verdict lands in the feed first, then the alert text, then the whisper and proof. Fixture mode (env
OVERHEARD_FIXTURE=1) answers from web/abroad/fixture_feed.json through the `_fx_*` functions.
"""
import base64, copy, json, mimetypes, os, re, tempfile, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

from overheard import abroad_alert, gmail, ingest, itinerary, learn, match, radar, rehearsal

ROOT = Path(__file__).resolve().parent.parent
ITINERARY_PATH = ROOT / "data" / "abroad" / "itinerary.json"
FIXTURE_FEED = ROOT / "web" / "abroad" / "fixture_feed.json"
UPLOADS = Path(tempfile.gettempdir()) / "overheard_abroad_uploads"
MEDIA_DIRS = [ROOT / "web" / "abroad" / "media", UPLOADS, ROOT / "data" / "abroad" / "media",
              ROOT / "data" / "abroad" / "rehearsal"]
MIME_KIND = {"audio": "audio", "image": "image", "video": "video", "text": "text"}

router = APIRouter(prefix="/api/abroad")
STATE = {"itinerary": None, "fp": [], "n_questions": 0, "lang": "Hindi", "events": [], "learned": []}
LOCK = threading.Lock()


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


# ---- fixture seams (OVERHEARD_FIXTURE=1): hand-written answers from fixture_feed.json ---------------------------------

def _fx_demo() -> tuple[dict, int, list[dict]]:
    fx = _fixture()
    return _fixture_itinerary(), fx["n_questions"], copy.deepcopy(fx["events"])


def _fx_ingest(texts: list[str], files: list[tuple[str, bytes, str]]) -> tuple[dict, int]:
    return _fixture_itinerary(), _fixture()["n_questions"]


def _fx_gmail() -> tuple[dict, int]:
    return _fixture_itinerary(), _fixture()["n_questions"]


def _fx_score(ev: dict, data: bytes, mime: str):
    """Fills `ev` in place: verdict plus receipt or alert, then a final status."""
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


def _fx_radar(today: str) -> list[dict]:
    return _fixture()["radar"]


def _fx_rehearse(booking_id: str | None) -> list[dict]:
    items = _fixture()["rehearsal"]
    if booking_id:
        items = [i for i in items if i["verdict"]["booking_id"] == booking_id] or items
    return items


def _fx_learn(ev: dict, booking_id: str, note: str) -> list[dict]:
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


def _fx_digest(today: str) -> dict:
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


# ---- real engine (default): itinerary, match, ingest, gmail, radar, rehearsal, learn, abroad_alert -------------

class NeedConsent(Exception):
    """The Gmail token is missing: the live consent is the user's step."""


SCORE_POOL = ThreadPoolExecutor(3)    # at most 3 Decision calls at once
WORK_POOL = ThreadPoolExecutor(12)    # one worker per input: waits on the score, then alert or receipt
RADAR_DIR = ROOT / "data" / "abroad" / "radar"
REHEARSAL_DIR = ROOT / "data" / "abroad" / "rehearsal"
MEDIA_MIME = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".jpg": "image/jpeg",
              ".jpeg": "image/jpeg", ".png": "image/png", ".mp4": "video/mp4", ".mov": "video/quicktime",
              ".txt": "text/plain", ".webm": "audio/webm", ".ogg": "audio/ogg"}


def _n_questions(it: dict, fp: list[dict], learned: list[dict]) -> int:
    return len(match.questions(it, fp, learned))


def _load_trip(it: dict) -> tuple[dict, int]:
    it.pop("note", None)
    fp = itinerary.fingerprint(it)
    with LOCK:
        STATE["fp"] = fp
    return it, _n_questions(it, fp, learn.load_learned(it["id"]))


def _engine_demo() -> tuple[dict, int, list[dict]]:
    if fixture_mode():
        return _fx_demo()
    it, n = _load_trip(itinerary.load(ITINERARY_PATH))
    return it, n, []


def _engine_ingest(texts: list[str], files: list[tuple[str, bytes, str]]) -> tuple[dict, int]:
    if fixture_mode():
        return _fx_ingest(texts, files)
    items = [t for t in texts if t.strip()] + [(data, mime) for _, data, mime in files]
    if not items:
        raise ValueError("paste a booking or attach a file")
    return _load_trip(ingest.parse(items, home_lang=STATE["lang"]))


def _engine_gmail() -> tuple[dict, int]:
    if fixture_mode():
        return _fx_gmail()
    if not (gmail.SECRETS / gmail.TOKEN_FILE).exists():
        raise NeedConsent("Gmail is not connected yet: run `python -m overheard.gmail --fetch` once and approve "
                          "read-only access for the lab inbox")
    mails = gmail.fetch_booking_emails()
    if not mails:
        raise ValueError("no booking emails found in the lab inbox")
    return _load_trip(ingest.parse(mails, source="gmail", home_lang=STATE["lang"]))


def _public(inp: dict) -> dict:
    return {k: v for k, v in inp.items() if k != "data_b64"}


def _score_event(ev: dict, inp: dict):
    """Verdict first, then the alert text, then the whisper and proof; or a receipt."""
    it, fp = STATE["itinerary"], STATE["fp"]
    learned = learn.load_learned(it["id"])
    v = SCORE_POOL.submit(match.score, inp, it, fp, learned).result()
    v["input_id"] = inp["id"]
    with LOCK:
        ev["verdict"] = v
    route, carbon = v["route"], None
    if route == "carbon" and v.get("booking_id"):
        carbon = abroad_alert.carbon_check(inp, v, it)
        with LOCK:
            v["carbon"] = carbon
        route = carbon["verdict"]
    if route == "alert" and v.get("booking_id"):
        def show(a):
            with LOCK:
                if ev["status"] != "dismissed":
                    ev["status"] = "alert"
                ev["alert"] = dict(a, carbon=carbon) if carbon else dict(a)
        show(abroad_alert.alert(inp, v, it, STATE["lang"], on_text=show))
    else:
        r = abroad_alert.receipt(inp, v, carbon)
        with LOCK:
            ev.update(status="silent", receipt=r)


def _run(ev: dict, inp: dict):
    def go():
        try:
            _score_event(ev, inp)
        except Exception as e:  # noqa: BLE001
            with LOCK:
                ev.update(status="silent", error=str(e)[:200],
                          receipt={"input_id": inp["id"], "gist": inp.get("name") or inp.get("title") or inp["kind"],
                                   "relevance": (ev.get("verdict") or {}).get("relevance", 0.0),
                                   "nearest_booking_id": None, "why": f"engine error: {str(e)[:120]}"})
    return WORK_POOL.submit(go)


def _play(inputs: list[dict]) -> list:
    futs = []
    for inp in inputs:
        ev = _push({"id": _new_id("ev"), "t": _now_iso(), "status": "scoring", "input": _public(inp)})
        futs.append(_run(ev, inp))
    return futs


def _engine_score(ev: dict, data: bytes, mime: str):
    if fixture_mode():
        return _fx_score(ev, data, mime)
    inp = dict(ev["input"])
    if mime.startswith("text"):
        inp.update(kind="text", text=data.decode("utf-8", "ignore"))
    else:
        inp["data_b64"] = base64.b64encode(data).decode()
    _score_event(ev, inp)


def _radar_inputs(today: str) -> list[dict]:
    """The snapshot for `today`, else the newest snapshot from the day before, else a live sweep (about 3 min)."""
    day = date.fromisoformat(today)
    for d in (day, day - timedelta(days=1)):
        p = RADAR_DIR / f"snapshot_{d.isoformat()}.json"
        if p.exists():
            return json.loads(p.read_text())["items"]
    items = radar.sweep(STATE["itinerary"], day)
    radar.save(items, STATE["itinerary"], day)
    return items


def _engine_radar(today: str) -> int:
    if fixture_mode():
        items = _fx_radar(today)
        _play_later(items)
        return len(items)
    inputs = [dict(i, id=_new_id("in_rd")) for i in _radar_inputs(today)]
    _play(inputs)
    return len(inputs)


def _rehearsal_input(item: dict) -> dict:
    path = REHEARSAL_DIR / item["media"]
    return {"id": _new_id("in_rh"), "kind": item["kind"], "origin": "rehearsal", "lang": item["lang"],
            "mime": MEDIA_MIME.get(path.suffix.lower(), "application/octet-stream"),
            "url": f"/api/abroad/media/{item['media']}", "name": item["id"], "rehearsal_id": item["id"],
            "expected_booking": item["booking_id"] if item["labels"].get(item["booking_id"]) else None,
            "data_b64": base64.b64encode(path.read_bytes()).decode()}


def _engine_rehearse(booking_id: str | None) -> int:
    if fixture_mode():
        items = _fx_rehearse(booking_id)
        _play_later(items)
        return len(items)
    ids = {b["id"] for b in STATE["itinerary"]["bookings"]}
    items = [i for i in rehearsal.load() if i["booking_id"] in ids]
    if booking_id:
        items = [i for i in items if i["booking_id"] == booking_id]
    else:   # one hit and one near miss per booking keeps the feed readable and the call count low
        pick = {}
        for i in items:
            pick.setdefault((i["booking_id"], bool(i["labels"].get(i["booking_id"]))), i)
        items = list(pick.values())
    _play([_rehearsal_input(i) for i in items])
    return len(items)


def _engine_learn(ev: dict, booking_id: str, note: str) -> list[dict]:
    if fixture_mode():
        return _fx_learn(ev, booking_id, note)
    it = STATE["itinerary"]
    qs = learn.learn({"event_id": ev["id"], "booking_id": booking_id, "note": note}, ev, it)
    added = learn.add_learned(it["id"], qs)
    with LOCK:
        STATE["n_questions"] = _n_questions(it, STATE["fp"], learn.load_learned(it["id"]))
    return added


def _engine_digest(today: str) -> dict:
    if fixture_mode():
        return _fx_digest(today)
    if not any(e["input"].get("origin") == "radar" for e in STATE["events"]):
        inputs = [dict(i, id=_new_id("in_rd")) for i in _radar_inputs(today)]
        for f in _play(inputs):
            try:
                f.result(timeout=150)
            except Exception:  # noqa: BLE001
                pass
    else:
        deadline = time.time() + 120
        while time.time() < deadline and any(e["status"] == "scoring" for e in STATE["events"]):
            time.sleep(0.5)
    with LOCK:
        events = copy.deepcopy(STATE["events"])
    return abroad_alert.digest(events, STATE["itinerary"], today)

# ---- routes -------------------------------------------------------------------------------------

def _missing(e: Exception) -> JSONResponse:
    if isinstance(e, NeedConsent):
        return JSONResponse({"error": str(e)}, status_code=409)
    if isinstance(e, (ValueError, KeyError)):
        return JSONResponse({"error": str(e)[:300]}, status_code=400)
    return JSONResponse({"error": f"engine error: {str(e)[:300]}"}, status_code=500)


def _no_trip() -> JSONResponse | None:
    if not fixture_mode() and not STATE["itinerary"]:
        return JSONResponse({"error": "load a trip first (POST /api/abroad/itinerary/demo)"}, status_code=400)
    return None


def _set_itinerary(it: dict, n: int, events: list[dict] | None = None) -> dict:
    with LOCK:
        STATE.update(itinerary=it, n_questions=n, events=events or [], learned=[])
    return {**it, "n_questions": n}


@router.post("/itinerary/demo")
async def itinerary_demo():
    try:
        it, n, events = await run_in_threadpool(_engine_demo)
    except Exception as e:  # noqa: BLE001
        return _missing(e)
    return _set_itinerary(it, n, events)


@router.post("/itinerary/ingest")
async def itinerary_ingest(files: list[UploadFile] | None = File(None), text: str = Form("")):
    blobs = [(f.filename or "file", await f.read(), f.content_type or "") for f in files or []]
    try:
        it, n = await run_in_threadpool(_engine_ingest, [text] if text else [], blobs)
    except Exception as e:  # noqa: BLE001
        return _missing(e)
    return _set_itinerary(it, n)


@router.post("/itinerary/gmail")
async def itinerary_gmail():
    try:
        it, n = await run_in_threadpool(_engine_gmail)
    except Exception as e:  # noqa: BLE001
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
    if (r := _no_trip()) is not None:
        return r
    data = await file.read()
    name = Path(file.filename or "input").name
    mime = file.content_type or ""
    if not mime or mime == "application/octet-stream":
        mime = MEDIA_MIME.get(Path(name).suffix.lower()) or mimetypes.guess_type(name)[0] or "application/octet-stream"
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
    if (r := _no_trip()) is not None:
        return r
    try:
        n = await run_in_threadpool(_engine_radar, today or date.today().isoformat())
    except Exception as e:  # noqa: BLE001
        return _missing(e)
    return {"n_items": n}


@router.post("/rehearse")
async def rehearse(booking_id: str = Form("")):
    if (r := _no_trip()) is not None:
        return r
    try:
        n = await run_in_threadpool(_engine_rehearse, booking_id or None)
    except Exception as e:  # noqa: BLE001
        return _missing(e)
    return {"n_items": n}


@router.post("/dismiss")
async def dismiss(event_id: str = Form(...), booking_id: str = Form(...), note: str = Form("")):
    ev = _find(event_id)
    if not ev:
        return JSONResponse({"error": f"no event {event_id}"}, status_code=404)
    try:
        added = await run_in_threadpool(_engine_learn, ev, booking_id, note)
    except Exception as e:  # noqa: BLE001
        return _missing(e)
    with LOCK:
        ev["status"] = "dismissed"
        STATE["learned"].extend(added)
    return {"added": added}


@router.get("/digest")
async def digest(today: str = ""):
    if (r := _no_trip()) is not None:
        return r
    try:
        return await run_in_threadpool(_engine_digest, today or date.today().isoformat())
    except Exception as e:  # noqa: BLE001
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
