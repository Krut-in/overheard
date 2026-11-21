"""Score any input (audio, image, video frame, text) against a trip fingerprint with gemini-decision-1, one call per input."""
import base64, time
from overheard import config
from overheard.gemini import client, log_call

MIME = {".wav": "audio/wav", ".mp3": "audio/mp3", ".ogg": "audio/ogg", ".webm": "audio/webm", ".m4a": "audio/mp4",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
        ".mp4": "video/mp4", ".mov": "video/quicktime"}

CHANGE_TYPES = {
    "delay": "Trains are delayed or running slowly.",
    "suspended": "Service is suspended or there are no trains on part of the line.",
    "skip": "Trains skip or do not stop at a station.",
    "reroute": "Trains run on a different line or route.",
    "platform": "Trains board on a different platform, track or level.",
    "entrance": "A station entrance, exit or elevator is closed.",
    "other": "No service change, or something else (ads, safety, door warnings, normal arrivals).",
}


def block(data: bytes, mime: str) -> dict:
    kind = mime.split("/")[0]
    b = {"type": kind, "data": base64.b64encode(data).decode(), "mime_type": mime}
    if kind in ("image", "video"):
        b["resolution"] = "low"
    return b


def core_questions(trip: dict) -> dict:
    stops = ", ".join([trip["board"], *trip.get("stops_between", []), trip["alight"]])
    return {
        "affects_trip": {"type": "noul", "instructions":
            f"A rider is taking the {trip['line']} train {trip['direction']} from {trip['board']} to {trip['alight']} "
            f"(stations on the way: {stops}). Does this input announce or show a service change that affects THIS "
            f"rider's trip: their line in their direction anywhere between their boarding and alighting stations, or "
            f"their boarding or alighting station itself? Normal arrivals, other lines, door warnings and ads are no."},
        "change_type": {"type": "choice", "instructions": "What kind of service change does this input describe?",
                        "criteria": CHANGE_TYPES},
    }


def score(inp: list | str, trip: dict, fingerprint: list[dict], label: str = "") -> dict:
    questions = core_questions(trip)
    for q in fingerprint:
        questions[q["id"]] = {"type": "noul", "instructions": q["q"]}
    t0 = time.time()
    r = client().decisions.create(model=config.DECISION, input=inp, questions=questions)
    dt = time.time() - t0
    log_call(config.DECISION, f"decide {label} ({len(questions)} q)", dt)
    ans = r.answers
    p = {k: ans[k].noul for k in ans if k != "change_type"}
    groups = {}
    for q in fingerprint:
        if q["id"] in p:
            groups.setdefault(q["group"], []).append((p[q["id"]], q["q"]))
    gmax = {g: max(v)[0] for g, v in groups.items()}
    mention = max(gmax.get("line", 0), gmax.get("station", 0))
    combo = gmax.get("combo", 0)
    # gate on the rider's line: station names alone fire on look-alike stations of other lines
    fp_score = gmax.get("line", 0) * max(combo, gmax.get("change", 0))
    direct = p["affects_trip"]
    relevance = config.DIRECT_WEIGHT * direct + (1 - config.DIRECT_WEIGHT) * fp_score
    top = sorted(((v, q) for g in groups.values() for v, q in g), reverse=True)[:5]
    ct = ans["change_type"]
    return {"relevance": round(relevance, 3), "direct": round(direct, 3), "fingerprint": round(fp_score, 3),
            "groups": {k: round(v, 3) for k, v in gmax.items()}, "change_type": ct.choice,
            "change_type_p": round(ct.confidence, 3), "top_hits": [{"p": round(v, 3), "q": q} for v, q in top],
            "latency_s": round(dt, 3), "n_questions": len(questions)}


def shrink(data: bytes, mime: str) -> tuple[bytes, str]:
    """Small payloads are 3x to 8x faster: audio to 16 kHz mono mp3, images to 1024 px JPEG."""
    import io, subprocess
    if mime.startswith("audio"):
        out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
                              "-b:a", "32k", "-f", "mp3", "pipe:1"], input=data, capture_output=True, check=True)
        return out.stdout, "audio/mp3"
    if mime.startswith("image"):
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        im.thumbnail((1024, 1024))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    return data, mime


def score_bytes(data: bytes, mime: str, trip: dict, fingerprint: list[dict], label: str = "",
                preamble: str | None = None) -> dict:
    data, mime = shrink(data, mime)
    pre = preamble or ("Something a rider heard over the station PA:" if mime.startswith("audio")
                       else "Something a rider photographed at a New York City subway station:")
    return score([{"type": "text", "text": pre}, block(data, mime)], trip, fingerprint, label=label)


def score_file(path: str, trip: dict, fingerprint: list[dict], preamble: str | None = None) -> dict:
    import pathlib
    p = pathlib.Path(path)
    return score_bytes(p.read_bytes(), MIME[p.suffix.lower()], trip, fingerprint, p.name, preamble)

