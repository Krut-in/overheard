"""Live MTA check: pull today's real subway service alerts (public GTFS-realtime JSON feed) and run each alert on the
rider's line through the same Decision 1 fingerprint, so real alerts get the same receipts and whispers."""
import json, re, time
import httpx

FEED = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json"
_CACHE = {"t": 0, "alerts": []}


def _text(tr, lang="en"):
    for t in (tr or {}).get("translation", []):
        if t.get("language") == lang:
            return t.get("text", "")
    return ""


def fetch_alerts(max_age_s: int = 120) -> list[dict]:
    if time.time() - _CACHE["t"] < max_age_s and _CACHE["alerts"]:
        return _CACHE["alerts"]
    d = httpx.get(FEED, headers={"User-Agent": "overheard-hackathon/0.1"}, timeout=20).json()
    now = time.time()
    out = []
    for e in d.get("entity", []):
        a = e.get("alert", {})
        periods = a.get("active_period", [])
        active = not periods or any(int(p.get("start", 0)) <= now <= int(p.get("end", now + 1)) for p in periods)
        if not active:
            continue
        routes = sorted({ie.get("route_id") for ie in a.get("informed_entity", []) if ie.get("route_id")})
        header = _text(a.get("header_text"))
        desc = re.sub(r"\s+", " ", _text(a.get("description_text")))[:600]
        out.append({"id": e.get("id"), "routes": routes, "header": header, "description": desc,
                    "stops": sorted({ie.get("stop_id") for ie in a.get("informed_entity", []) if ie.get("stop_id")})})
    _CACHE.update(t=time.time(), alerts=out)
    return out


def on_line(alerts: list[dict], line: str) -> list[dict]:
    return [a for a in alerts if line.upper() in a["routes"]]


def as_text(a: dict) -> str:
    return f"MTA service alert. {a['header']} {a['description']}".strip()
