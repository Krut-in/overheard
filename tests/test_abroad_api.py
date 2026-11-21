"""Ticket F: digest rules (pure) and /api/abroad route shapes in real mode, with every Gemini call stubbed."""
import time

import pytest
from fastapi.testclient import TestClient

from overheard import abroad_alert, api_abroad, itinerary, learn, match

IT = itinerary.load(api_abroad.ITINERARY_PATH)


def ev(status, booking_id, rel=0.9):
    e = {"id": f"ev_{booking_id}_{status}", "t": "2026-11-21T10:00:00-05:00", "status": status,
         "input": {"id": "in", "kind": "news", "origin": "radar"},
         "verdict": {"booking_id": booking_id, "relevance": rel}}
    if status == "alert":
        e["alert"] = {"booking_id": booking_id}
    else:
        e["receipt"] = {"input_id": "in", "gist": "g", "relevance": rel, "nearest_booking_id": booking_id, "why": "w"}
    return e


def test_digest_urgent_is_alert_on_booking_starting_within_two_days():
    d = abroad_alert.digest([ev("alert", "flight_out"), ev("alert", "train_ams")], IT, "2026-11-22")
    assert [e["alert"]["booking_id"] for e in d["urgent"]] == ["flight_out"]   # starts 24 Nov
    assert d["today"] == []


def test_digest_today_lists_alerts_on_active_bookings_and_counts_silence():
    evs = [ev("alert", "hotel_paris"), ev("silent", "train_ams", 0.1), ev("silent", "hotel_ams", 0.2)]
    d = abroad_alert.digest(evs, IT, "2026-11-26")   # hotel_paris runs 25 to 28 Nov
    assert [e["alert"]["booking_id"] for e in d["today"]] == ["hotel_paris"]
    assert d["urgent"] == [] and d["silent_count"] == 2 and len(d["receipts_sample"]) == 2
    assert set(d) == {"date", "itinerary_id", "urgent", "today", "silent_count", "receipts_sample"}


def test_digest_ignores_receipts_and_past_bookings():
    d = abroad_alert.digest([ev("silent", "flight_out"), ev("alert", "flight_out")], IT, "2026-11-28")
    assert d["urgent"] == [] and d["today"] == []


def test_why_names_top_hit_of_the_chosen_booking():
    v = {"booking_id": "train_ams", "relevance": 0.3,
         "top_hits": [{"p": 0.7, "q": "other?", "booking_id": "hotel_ams"}, {"p": 0.3, "q": "9315?", "booking_id": "train_ams"}]}
    assert abroad_alert.why(v) == "top hit 0.30: 9315?"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("OVERHEARD_FIXTURE", raising=False)
    monkeypatch.setattr(itinerary, "fingerprint", lambda it: [{"id": "q1", "booking_id": "train_ams", "group": "operator", "q": "Eurostar?"}])
    monkeypatch.setattr(learn, "LEARNED_DIR", tmp_path)

    def score(inp, it, fp, learned=[]):  # noqa: B006
        rel = 0.95 if "9315" in inp.get("text", "") else 0.1
        if any(q["group"] == "not" for q in learned):
            rel = 0.05
        return {"input_id": inp["id"], "relevance": rel, "booking_id": "train_ams", "per_booking": {"train_ams": rel},
                "change_type": "cancelled", "top_hits": [{"p": rel, "q": "Eurostar?", "booking_id": "train_ams"}],
                "route": "alert" if rel >= 0.8 else "silence", "latency_s": 0.01, "n_questions": 9}
    monkeypatch.setattr(match, "score", score)
    monkeypatch.setattr(abroad_alert, "alert", lambda inp, v, it, lang, on_text=None: {
        "input_id": inp["id"], "booking_id": v["booking_id"], "change": "c", "action": "a",
        "translated": {"change": "c", "action": "a", "lang": lang}, "whisper_url": "/api/abroad/media/w.wav",
        "proof": {"kind": "quote", "url": None, "quote": "q"}})
    monkeypatch.setattr(abroad_alert, "gist", lambda inp: "gist")
    monkeypatch.setattr(learn, "learn", lambda d, e, it: [{"id": f"not__{d['booking_id']}__x", "booking_id": d["booking_id"],
                                                          "group": "not", "q": "Is it another train?"}])
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(api_abroad.router)
    with TestClient(app) as c:
        yield c


def wait_feed(c, n):
    for _ in range(100):
        evs = c.get("/api/abroad/feed").json()["events"]
        if len(evs) >= n and all(e["status"] != "scoring" for e in evs):
            return evs
        time.sleep(0.05)
    raise AssertionError(evs)


def test_input_before_trip_is_400(client):
    api_abroad.STATE["itinerary"] = None
    assert client.post("/api/abroad/input", files={"file": ("a.txt", b"x", "text/plain")}).status_code == 400


def test_real_mode_alert_then_dismiss_then_silent(client):
    r = client.post("/api/abroad/itinerary/demo").json()
    assert r["id"] == IT["id"] and r["n_questions"] > 0
    text = b"Greve: Eurostar 9315 du 28 novembre supprime"
    posted = client.post("/api/abroad/input", files={"file": ("n.txt", text, "text/plain")}).json()
    assert posted["status"] == "scoring" and "data_b64" not in posted["input"]
    evs = wait_feed(client, 1)
    e = evs[0]
    assert e["status"] == "alert" and e["alert"]["booking_id"] == "train_ams" and e["verdict"]["relevance"] >= 0.8
    d = client.post("/api/abroad/dismiss", data={"event_id": e["id"], "booking_id": "train_ams"}).json()
    assert d["added"][0]["group"] == "not"
    client.post("/api/abroad/input", files={"file": ("n.txt", text, "text/plain")})
    evs = wait_feed(client, 2)
    assert evs[0]["status"] == "silent" and evs[0]["verdict"]["relevance"] < 0.4
    assert evs[0]["receipt"]["why"].startswith("top hit")


def test_gmail_without_token_is_409(client, monkeypatch, tmp_path):
    from overheard import gmail
    monkeypatch.setattr(gmail, "SECRETS", tmp_path)
    r = client.post("/api/abroad/itinerary/gmail")
    assert r.status_code == 409 and "Gmail" in r.json()["error"]
