"""Ticket B checks: pure merge/dedupe/normalise tests, then the 6 sample emails parsed live by Neon."""
import json
import os
import unicodedata
from pathlib import Path

import pytest

from overheard import ingest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "data/abroad/itinerary.json").read_text())
EMAILS = ROOT / "data/abroad/emails"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.casefold().split())


def raw(**kw):
    b = {"kind": "train", "title": "t", "operator": "Eurostar", "number": "9315", "ref": "EUSMPL4",
         "start": "2026-11-28T09:25+01:00", "end": "2026-11-28T12:43+01:00", "from_place": "Paris Gare du Nord",
         "to_place": "Amsterdam Centraal", "city": "Amsterdam", "country": "NL", "langs": ["fr", "nl"], "details": ""}
    b.update(kw)
    return b


# ---- pure: no network ----

def test_flight_numbers_are_normalised():
    assert ingest.norm_number("flight", "AF023") == "AF 23"
    assert ingest.norm_number("flight", "kl641") == "KL 641"
    assert ingest.norm_number("train", "Eurostar 9315") == "9315"
    assert ingest.norm_number("hotel", "n/a") == ""


def test_merge_dedupes_by_ref_sorts_by_start_and_sets_source():
    a = raw(ref="EUSMPL4")
    b = raw(ref="eusmpl4 ", details="Coach 14, seat 61")  # same booking seen twice, second is richer
    c = raw(kind="flight", operator="Air France", number="AF23", ref="SMPL7Q", start="2026-11-24T19:30-05:00",
            end="2026-11-25T08:45+01:00")
    out = ingest.merge([(a, "paste"), (b, "gmail"), (c, "upload")])
    assert [x["ref"] for x in out] == ["SMPL7Q", "EUSMPL4"]
    assert out[0]["number"] == "AF 23" and out[0]["source"] == "upload"
    assert out[1]["details"] == "Coach 14, seat 61"
    assert len({x["id"] for x in out}) == len(out)


def test_merge_without_ref_dedupes_on_kind_number_and_date():
    a = raw(ref="", number="9315")
    b = raw(ref="", number="9315", start="2026-11-28T09:25:00+01:00")
    c = raw(ref="", number="9317")
    assert len(ingest.merge([(a, "paste"), (b, "paste"), (c, "paste")])) == 2


def test_ids_follow_kind_and_are_unique():
    out = ingest.merge([(raw(kind="hotel", ref="H1", city="Paris"), "paste"),
                        (raw(kind="hotel", ref="H2", city="Paris", start="2026-11-29T15:00+01:00"), "paste")])
    assert all(x["id"].startswith("hotel_") for x in out)
    assert out[0]["id"] != out[1]["id"]


# ---- live: the 6 sample emails through Neon ----

live = pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY") and not (ROOT / ".env").exists(),
                          reason="needs GEMINI_API_KEY")


@pytest.fixture(scope="module")
def parsed():
    texts = [p.read_text() for p in sorted(EMAILS.glob("*.txt"))]
    assert len(texts) == 6, "expected 6 sample emails"
    return ingest.parse(texts, source="gmail")


@live
def test_six_emails_match_fixture(parsed):
    want = {b["ref"]: b for b in FIXTURE["bookings"]}
    got = {b["ref"]: b for b in parsed["bookings"]}
    assert set(got) == set(want), f"refs differ: got {sorted(got)}"
    for ref, w in want.items():
        g = got[ref]
        assert g["kind"] == w["kind"], ref
        assert norm(g["operator"]) == norm(w["operator"]), (ref, g["operator"])
        assert g["number"] == w["number"], (ref, g["number"])
        assert g["start"][:10] == w["start"][:10], (ref, g["start"])
        assert g["source"] == "gmail"


@live
def test_itinerary_shape(parsed):
    assert set(parsed) >= {"id", "traveller", "home_lang", "bookings"}
    starts = [b["start"] for b in parsed["bookings"]]
    assert starts == sorted(starts, key=ingest.start_key)
    for b in parsed["bookings"]:
        assert set(b) >= {"id", "kind", "title", "operator", "number", "ref", "start", "end", "from_place",
                          "to_place", "city", "country", "langs", "details", "source"}
