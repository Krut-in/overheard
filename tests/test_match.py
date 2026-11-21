"""Pure tests for overheard.match.combine: the per-booking formula, the not group, the news date gate, argmax booking."""
import json
from pathlib import Path
import pytest
from overheard.match import combine

IT = json.loads((Path(__file__).resolve().parent.parent / "data/abroad/itinerary.json").read_text())

FP = [
    {"id": "train_ams__op", "booking_id": "train_ams", "group": "operator", "q": "Mentions Eurostar 9315?"},
    {"id": "train_ams__pl", "booking_id": "train_ams", "group": "place", "q": "Mentions Gare du Nord?"},
    {"id": "train_ams__combo", "booking_id": "train_ams", "group": "combo", "q": "Says Eurostar 9315 is cancelled?"},
    {"id": "train_ams__chg", "booking_id": "train_ams", "group": "change", "q": "Mentions a strike?"},
    {"id": "flight_out__op", "booking_id": "flight_out", "group": "operator", "q": "Mentions Air France AF 23?"},
    {"id": "flight_out__combo", "booking_id": "flight_out", "group": "combo", "q": "Says AF 23 is delayed?"},
]
NOT_Q = [{"id": "train_ams__not1", "booking_id": "train_ams", "group": "not", "q": "Is it about Eurostar 9317?"}]


def answers(**p):
    base = {q["id"]: 0.01 for q in FP} | {f"affects__{b['id']}": 0.01 for b in IT["bookings"]}
    return base | p | {"change_type": "strike"}


TEXT = {"id": "in1", "kind": "text", "origin": "sample", "text": "x"}


def test_per_booking_formula():
    a = answers(train_ams__op=0.9, train_ams__pl=0.5, train_ams__combo=0.6, train_ams__chg=0.8,
                affects__train_ams=0.5)
    v = combine(a, IT, FP, [], TEXT)
    # fp = max(0.9, 0.5) x max(0.6, 0.8) = 0.72 ; s = 0.3 x 0.5 + 0.7 x 0.72 = 0.654
    assert v["per_booking"]["train_ams"] == pytest.approx(0.654, abs=1e-3)
    assert v["booking_id"] == "train_ams"
    assert v["relevance"] == pytest.approx(0.654, abs=1e-3)
    assert v["route"] == "carbon"


def test_change_group_is_shared_across_bookings():
    # a strike question tagged with train_ams still counts as "p change" for the flight
    a = answers(flight_out__op=0.9, train_ams__chg=0.9, affects__flight_out=0.9)
    v = combine(a, IT, FP, [], TEXT)
    # 0.3 x 0.9 + 0.7 x (0.9 x 0.9) = 0.837
    assert v["per_booking"]["flight_out"] == pytest.approx(0.837, abs=1e-3)
    assert v["route"] == "alert"


def test_argmax_booking_and_silence():
    a = answers(flight_out__op=0.3, flight_out__combo=0.3, train_ams__op=0.2, train_ams__combo=0.1)
    v = combine(a, IT, FP, [], TEXT)
    assert v["booking_id"] == "flight_out"
    assert v["route"] == "silence"
    assert set(v["per_booking"]) == {b["id"] for b in IT["bookings"]}


def test_not_group_suppresses_its_booking():
    a = answers(train_ams__op=0.99, train_ams__combo=0.99, affects__train_ams=0.99, train_ams__not1=0.9)
    v = combine(a, IT, FP, NOT_Q, TEXT)
    # s = 0.99 x 0.99 ... ~= 0.983 x (1 - 0.9) = 0.098
    assert v["per_booking"]["train_ams"] == pytest.approx(0.0983, abs=1e-3)
    assert v["route"] == "silence"


def test_no_learned_questions_means_no_penalty():
    a = answers(train_ams__op=0.99, train_ams__combo=0.99, affects__train_ams=0.99)
    v = combine(a, IT, FP, [], TEXT)
    assert v["per_booking"]["train_ams"] > 0.95


def news(dates):
    return {"id": "n1", "kind": "news", "origin": "radar", "text": "x", "dates": dates}


def test_news_date_gate_blocks_other_dates():
    a = answers(train_ams__op=0.99, train_ams__combo=0.99, affects__train_ams=0.99)
    v = combine(a, IT, FP, [], news(["2026-12-05"]))
    assert v["per_booking"]["train_ams"] == 0
    assert v["route"] == "silence"


def test_news_date_gate_allows_day_before_start():
    a = answers(train_ams__op=0.99, train_ams__combo=0.99, affects__train_ams=0.99)
    v = combine(a, IT, FP, [], news(["2026-11-27"]))   # train is 2026-11-28; minus one day is in
    assert v["per_booking"]["train_ams"] > 0.95
    v = combine(a, IT, FP, [], news(["2026-11-26"]))   # two days before is out
    assert v["per_booking"]["train_ams"] == 0


def test_news_without_dates_is_not_gated():
    a = answers(train_ams__op=0.99, train_ams__combo=0.99, affects__train_ams=0.99)
    assert combine(a, IT, FP, [], news([]))["per_booking"]["train_ams"] > 0.95


def test_verdict_shape_and_top_hits():
    a = answers(train_ams__op=0.9, train_ams__combo=0.8)
    v = combine(a, IT, FP, [], TEXT)
    assert set(v) >= {"input_id", "relevance", "booking_id", "per_booking", "change_type", "top_hits",
                      "route", "latency_s", "n_questions"}
    assert v["input_id"] == "in1"
    assert v["change_type"] == "strike"
    assert v["top_hits"][0] == {"p": 0.9, "q": "Mentions Eurostar 9315?", "booking_id": "train_ams"}
