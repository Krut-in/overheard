"""Overheard demo server: trip in, every input scored against the trip fingerprint, receipts and alerts in a live feed.

Run: .venv/bin/uvicorn server:app --port 8000   then open http://localhost:8000
"""
import base64, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from overheard import config, alert, video
from overheard.decide import MIME, score_bytes, shrink
from overheard.fingerprint import build_fingerprint
from overheard.trip import extract_trip

ROOT = Path(__file__).resolve().parent
app = FastAPI()
pool = ThreadPoolExecutor(12)
STATE = {"trip": None, "fp": [], "events": [], "lang": "Hindi"}
LOCK = threading.Lock()


def b64(data: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def guess_mime(f: UploadFile) -> str:
    ext = Path(f.filename or "").suffix.lower()
    return MIME.get(ext) or f.content_type or "application/octet-stream"


def new_event(**kw) -> dict:
    ev = {"id": uuid.uuid4().hex[:8], "t": time.strftime("%H:%M:%S"), "status": "scoring", **kw}
    with LOCK:
        STATE["events"].insert(0, ev)
    return ev


@app.post("/api/trip")
async def set_trip(route: str = Form(""), file: UploadFile | None = File(None)):
    data = await file.read() if file else None
    mime = guess_mime(file) if file else None
    if data and mime and mime.startswith("audio"):
        data, mime = shrink(data, mime)
    t0 = time.time()
    trip = extract_trip(route or None, data, mime or "image/jpeg")
    fp = build_fingerprint(trip)
    with LOCK:
        STATE.update(trip=trip, fp=fp, events=[])
    return {"trip": trip, "n_questions": len(fp) + 2, "seconds": round(time.time() - t0, 1),
            "sample": [q["q"] for q in fp[::max(1, len(fp) // 8)]][:8]}


@app.post("/api/lang")
async def set_lang(lang: str = Form(...)):
    STATE["lang"] = lang
    return {"lang": lang}


def run_alert(ev: dict, data: bytes, mime: str):
    trip, lang = STATE["trip"], STATE["lang"]
    ch = alert.extract_change(data, mime, trip)
    ev["change"] = ch
    tr = alert.translate(ch, lang)
    ev["translated"] = tr
    ev["status"] = "alert"
    jobs = {"audio": pool.submit(alert.whisper, tr["whisper"])}
    if mime.startswith("image"):
        jobs["photo"] = pool.submit(alert.annotate, data, mime, ch["quote"], tr["change"])
    ev["whisper_wav"] = b64(jobs["audio"].result(), "audio/wav")
    if "photo" in jobs:
        try:
            img = jobs["photo"].result()
            if img:
                ev["annotated"] = b64(img, "image/png")
        except Exception as e:  # noqa: BLE001
            ev["annotate_error"] = str(e)[:200]


def process(ev: dict, data: bytes, mime: str):
    try:
        cap = pool.submit(alert.caption, data, mime)
        s = score_bytes(data, mime, STATE["trip"], STATE["fp"], label=ev["name"])
        ev["scores"] = s
        rel = s["relevance"]
        if rel >= config.ALERT_AT:
            ev["route"] = "alert"
            run_alert(ev, data, mime)
        elif rel >= config.CONFLICT_AT:
            ev["route"] = "carbon"
            ev["status"] = "carbon"
            v = alert.carbon_band(data, mime, STATE["trip"], s)
            ev["carbon"] = v
            if v["relevant"]:
                run_alert(ev, data, mime)
            else:
                ev["status"] = "silent"
        else:
            ev["route"] = "silence"
            ev["status"] = "silent"
        try:
            ev["caption"] = cap.result(timeout=20)
        except Exception:  # noqa: BLE001
            ev["caption"] = s["change_type"]
    except Exception as e:  # noqa: BLE001
        ev["status"] = "error"
        ev["error"] = str(e)[:300]


@app.post("/api/input")
async def add_input(file: UploadFile = File(...)):
    if not STATE["trip"]:
        return JSONResponse({"error": "set a trip first"}, status_code=400)
    raw = await file.read()
    mime = guess_mime(file)
    if mime.startswith("video"):
        ev = new_event(name=file.filename, kind="video")
        pool.submit(video.process_video, ev, raw, file.filename, STATE, pool, process_frame_hit)
        return {"id": ev["id"]}
    data, mime = shrink(raw, mime)
    ev = new_event(name=file.filename, kind=mime.split("/")[0],
                   preview=b64(data, mime) if mime.startswith("image") else None)
    pool.submit(process, ev, data, mime)
    return {"id": ev["id"]}


def process_frame_hit(ev: dict, frame: bytes):
    """Video: the best frame of a relevant moment goes through the normal alert path."""
    run_alert(ev, frame, "image/jpeg")


@app.post("/api/conflict")
async def conflict():
    alerts = [e for e in STATE["events"] if e.get("change")][:2]
    if len(alerts) < 2:
        return JSONResponse({"error": "need two alerts"}, status_code=400)
    second, first = alerts[0], alerts[1]
    fmt = lambda e: {"source": e["kind"], "name": e["name"], "time": e["t"], **e["change"]}
    v = alert.carbon_conflict(STATE["trip"], fmt(first), fmt(second))
    v["first"], v["second"] = first["name"], second["name"]
    if v["trust"] in ("first", "second"):
        v["trusted_change"] = (first if v["trust"] == "first" else second)["change"]
    try:
        v["translated"] = alert.translate({"change": v["explanation"], "action": v["do_now"]}, STATE["lang"])
        v["whisper_wav"] = b64(alert.whisper(v["translated"]["whisper"]), "audio/wav")
    except Exception:  # noqa: BLE001
        pass
    return v


@app.get("/api/feed")
async def feed():
    return {"trip": STATE["trip"], "lang": STATE["lang"], "events": STATE["events"][:40]}


@app.get("/")
async def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/media", StaticFiles(directory=ROOT / "data"), name="media")
app.mount("/clips", StaticFiles(directory=ROOT / "logs"), name="clips")
