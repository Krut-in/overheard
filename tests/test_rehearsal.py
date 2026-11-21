"""Checks for the saved rehearsal set: schema, label balance per booking, languages, and playable media."""
import json, subprocess
from pathlib import Path
import pytest
from overheard import rehearsal

ROOT = Path(__file__).resolve().parent.parent
IT = json.loads((ROOT / "data/abroad/itinerary.json").read_text())
BOOKINGS = [b["id"] for b in IT["bookings"]]


@pytest.fixture(scope="module")
def items():
    return rehearsal.load()


def test_check_flags_unbalanced_set():
    good = [{"id": f"x{i}", "booking_id": "b1", "lang": "fr", "kind": "audio", "script": "s", "media": f"x{i}.mp3",
             "labels": {"b1": i < 2}, "why": "w"} for i in range(4)]
    it = {"bookings": [{"id": "b1"}]}
    assert rehearsal.check(good, it, per_booking=4) == []
    bad = [dict(g, labels={"b1": True}) for g in good]
    assert any("balance" in p for p in rehearsal.check(bad, it, per_booking=4))
    missing = [dict(g, labels={}) for g in good]
    assert any("labels" in p for p in rehearsal.check(missing, it, per_booking=4))


def test_schema_and_balance(items):
    assert rehearsal.check(items, IT) == []


def test_size_and_mix(items):
    assert len(items) >= 36
    assert sum(i["kind"] == "audio" for i in items) >= 24
    assert sum(i["kind"] == "image" for i in items) >= 12
    assert {"fr", "nl", "en"} <= {i["lang"] for i in items}
    assert len({i["id"] for i in items}) == len(items)
    for b in BOOKINGS:
        mine = [i for i in items if i["booking_id"] == b]
        assert len(mine) >= 6
        assert sum(i["labels"][b] for i in mine) * 2 == len(mine)


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                         capture_output=True, text=True)
    assert out.returncode == 0, f"ffprobe failed on {path.name}: {out.stderr[:200]}"
    return json.loads(out.stdout)


def test_media_exists_and_plays(items):
    for i in items:
        p = rehearsal.DIR / i["media"]
        assert p.exists(), f"missing {i['media']}"
        info = _probe(p)
        if i["kind"] == "audio":
            assert p.suffix == ".mp3"
            assert float(info["format"]["duration"]) > 1.0, i["id"]
        else:
            assert p.suffix == ".jpg"
            assert p.stat().st_size < 300_000, f"{p.name} is {p.stat().st_size} bytes"
            assert info["streams"][0]["width"] > 200
