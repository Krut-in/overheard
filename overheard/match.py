"""Score one Input against the itinerary fingerprint with one gemini-decision-1 call, then combine per booking (pure)."""
import base64, json, time
from datetime import date, datetime, timedelta
from overheard import config, learn
from overheard.decide import block, shrink
from overheard.gemini import client, log_call, ROOT
from overheard.itinerary import Booking, Fingerprint, Input, Itinerary, TaggedQuestion, Verdict, fingerprint, load

# Abroad change types (the subway CHANGE_TYPES in decide.py talk about trains and lines only).
CHANGE_TYPES = {
    "cancelled": "A flight, train, visit or service is cancelled (supprime, annule, geannuleerd, cancelled).",
    "closure": "A place is closed: a museum, station, entrance, hotel area or road (ferme, gesloten, closed).",
    "delay": "A flight or train is delayed or late (retard, vertraging, delayed).",
    "gate": "A different gate, platform, track or terminal (porte, voie, spoor, perron, gate, platform).",
    "other": "No disruption, or something else: ads, safety notices, normal boarding or arrival info.",
    "schedule": "A changed time or timetable, or a replacement service (bus de substitution, vervangend vervoer).",
    "strike": "A strike or industrial action (greve, mouvement social, staking, strike).",
}

KIND_WORDS = {"flight": "flight", "train": "train", "hotel": "hotel stay", "ticket": "timed entry ticket"}


def _day(iso: str) -> date:
    return datetime.fromisoformat(iso).date()


def affects_question(b: Booking) -> str:
    where = b["from_place"] + (f" to {b['to_place']}" if b["to_place"] else "")
    svc = f"{b['operator']} {b['number']}".strip()
    when = f"{_day(b['start']).strftime('%d %B %Y')}"
    extra = f" ({b['details']})" if b.get("details") else ""
    return (f"A traveller holds this {KIND_WORDS.get(b['kind'], b['kind'])}: {svc}, {where}, on {when}{extra}. "
            f"Does this input announce or show a disruption (strike, cancellation, delay, gate or platform change, "
            f"closure, schedule change) that hits THIS booking: this operator with this exact service number, or "
            f"its places, on its date? Other flight or train numbers, other places, other dates, ads and normal "
            f"information are no.")


def questions(it: Itinerary, fp: Fingerprint, learned: list[TaggedQuestion]) -> dict:
    qs = {q["id"]: {"type": "noul", "instructions": q["q"]} for q in [*fp, *learned]}
    for b in it["bookings"]:
        qs[f"affects__{b['id']}"] = {"type": "noul", "instructions": affects_question(b)}
    qs["change_type"] = {"type": "choice", "instructions": "What kind of travel disruption does this input describe?",
                         "criteria": CHANGE_TYPES}
    return qs


def _in_window(dates: list[str], b: Booking) -> bool:
    lo = _day(b["start"]) - timedelta(days=config.NEWS_DATE_SLACK_DAYS)
    hi = _day(b["end"])
    return any(lo <= date.fromisoformat(d[:10]) <= hi for d in dates)


def combine(answers: dict, it: Itinerary, fp: Fingerprint, learned: list[TaggedQuestion], inp: Input,
            latency_s: float = 0.0) -> Verdict:
    """answers maps question id to its noul probability, plus "change_type" to the chosen key. Pure."""
    allq = [*fp, *learned]
    gmax: dict[tuple[str, str], float] = {}
    change = 0.0
    for q in allq:
        p = answers.get(q["id"])
        if p is None:
            continue
        key = (q["booking_id"], q["group"])
        gmax[key] = max(gmax.get(key, 0.0), p)
        if q["group"] == "change":
            change = max(change, p)   # "p change" is shared: a strike is a strike whichever booking asked
    w = config.DIRECT_WEIGHT
    dates = inp.get("dates") or []
    per = {}
    for b in it["bookings"]:
        bid = b["id"]
        g = lambda grp: gmax.get((bid, grp), 0.0)  # noqa: E731
        fp_b = max(g("operator"), g("place")) * max(g("combo"), change)
        s = (w * answers.get(f"affects__{bid}", 0.0) + (1 - w) * fp_b) * (1 - learn.not_effective(g("not")))
        if inp.get("kind") == "news" and dates and not _in_window(dates, b):
            s = 0.0
        per[bid] = round(s, 4)
    best = max(per, key=per.get) if per else None
    rel = per[best] if best else 0.0
    route = "alert" if rel >= config.ALERT_AT else "carbon" if rel >= config.CONFLICT_AT else "silence"
    hits = sorted(((answers[q["id"]], q["q"], q["booking_id"]) for q in allq
                   if q["id"] in answers and q["group"] != "not"),
                  key=lambda h: (-h[0], h[2] != best))[:5]   # ties at 0.99: the winning booking's hits first
    return {"input_id": inp["id"], "relevance": rel, "booking_id": best if rel > 0 else None, "per_booking": per,
            "change_type": answers.get("change_type", "other"),
            "top_hits": [{"p": round(p, 3), "q": q, "booking_id": bid} for p, q, bid in hits],
            "route": route, "latency_s": round(latency_s, 3), "n_questions": len(allq) + len(it["bookings"]) + 1}


PREAMBLE = {
    "audio": "Something a traveller heard over a station or airport PA in France or the Netherlands:",
    "image": "Something a traveller photographed on a trip in France or the Netherlands (sign, poster or board):",
    "video": "A short video a traveller filmed on a trip in France or the Netherlands:",
    "text": "Something a traveller read or was told on a trip in France or the Netherlands:",
}


def to_blocks(inp: Input) -> list[dict]:
    if inp["kind"] == "news":
        head = f"A news item found for the traveller (published {inp.get('published', 'unknown')}):"
        return [{"type": "text", "text": f"{head}\n{inp['text']}"}]
    if inp["kind"] == "text" or "data_b64" not in inp:
        return [{"type": "text", "text": f"{PREAMBLE['text']}\n{inp['text']}"}]
    data, mime = shrink(base64.b64decode(inp["data_b64"]), inp["mime"])
    return [{"type": "text", "text": PREAMBLE.get(inp["kind"], PREAMBLE["text"])}, block(data, mime)]


def score(inp: Input, it: Itinerary, fp: Fingerprint, learned: list[TaggedQuestion] = []) -> Verdict:  # noqa: B006
    qs = questions(it, fp, learned)
    blocks = to_blocks(inp)
    t0 = time.time()
    for attempt in range(3):
        try:
            r = client().decisions.create(model=config.DECISION, input=blocks, questions=qs)
            break
        except Exception as e:  # noqa: BLE001
            if attempt < 2 and any(c in str(e) for c in ("503", "500", "UNAVAILABLE", "overloaded")):
                time.sleep(1.5 * (attempt + 1))
                continue
            log_call(config.DECISION, f"abroad match {inp['id']} ({len(qs)} q) ERROR {str(e)[:80]}",
                     time.time() - t0, error=True)
            raise
    dt = time.time() - t0
    log_call(config.DECISION, f"abroad match {inp['id']} {inp['kind']} ({len(qs)} q)", dt)
    ans = {k: (v.choice if k == "change_type" else v.noul) for k, v in r.answers.items()}
    v = combine(ans, it, fp, learned, inp, latency_s=dt)
    v["n_questions"] = len(qs)
    return v


def _file_input(path: str) -> Input:
    from pathlib import Path
    from overheard.decide import MIME
    p = Path(path)
    mime = MIME.get(p.suffix.lower(), "text/plain")
    if mime == "text/plain":
        return {"id": p.stem, "kind": "text", "origin": "upload", "text": p.read_text()}
    return {"id": p.stem, "kind": mime.split("/")[0], "origin": "upload", "mime": mime,
            "data_b64": base64.b64encode(p.read_bytes()).decode()}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Score one input against the itinerary and print the Verdict.")
    ap.add_argument("--text")
    ap.add_argument("--file")
    ap.add_argument("--news", action="store_true", help="treat --text as a news item")
    ap.add_argument("--dates", default="", help="comma-separated YYYY-MM-DD dates the news item mentions")
    ap.add_argument("--itinerary", default=str(ROOT / "data" / "abroad" / "itinerary.json"))
    a = ap.parse_args()
    it = load(a.itinerary)
    fp = fingerprint(it)
    if a.file:
        inp = _file_input(a.file)
    else:
        inp = {"id": "cli", "kind": "news" if a.news else "text", "origin": "sample", "text": a.text,
               "dates": [d for d in a.dates.split(",") if d]}
    print(json.dumps(score(inp, it, fp), indent=1, ensure_ascii=False))
