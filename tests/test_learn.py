"""Tests for overheard/learn.py: learned-question storage, the (1 - not) factor, and learn() with a stubbed Hydrogen."""
import json
import pytest
from overheard import learn

IT = {"id": "demo", "bookings": [
    {"id": "t3", "kind": "train", "title": "7 train Flushing-bound, Grand Central-42 St to Flushing-Main St",
     "operator": "MTA", "number": "7", "from_place": "Grand Central-42 St", "to_place": "Flushing-Main St",
     "start": "", "end": "", "details": "Flushing-bound"},
    {"id": "hotel", "kind": "hotel", "title": "Hotel", "operator": "Hotel", "number": "", "from_place": "",
     "to_place": "", "start": "", "end": "", "details": ""}]}
EVENT = {"id": "ev1", "input": {"id": "in1", "kind": "text", "text": "Manhattan-bound 7 skips 111 St"},
         "verdict": {"top_hits": [{"p": 0.98, "q": "Does it mention the 7 train?", "booking_id": "t3"}]}}


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(learn, "LEARNED_DIR", tmp_path)
    return tmp_path


def q(i, b="t3"):
    return {"id": f"not__{b}__{i}", "booking_id": b, "group": "not", "q": f"question {i}?"}


def test_load_learned_is_empty_when_nothing_saved():
    assert learn.load_learned("demo") == []


def test_save_then_load_round_trips(tmp_store):
    learn.save_learned("demo", [q(1), q(2)])
    assert learn.load_learned("demo") == [q(1), q(2)]
    assert json.loads((tmp_store / "demo.json").read_text()) == [q(1), q(2)]


def test_add_learned_appends_and_skips_duplicate_ids():
    learn.save_learned("demo", [q(1)])
    added = learn.add_learned("demo", [q(1), q(2)])
    assert added == [q(2)]
    assert learn.load_learned("demo") == [q(1), q(2)]


def test_not_score_is_zero_without_learned_questions():
    assert learn.not_score({"x": 0.9}, [], "t3") == 0


def test_not_score_is_max_over_that_bookings_questions_only():
    p = {q(1)["id"]: 0.2, q(2)["id"]: 0.7, q(3, "hotel")["id"]: 0.99}
    assert learn.not_score(p, [q(1), q(2), q(3, "hotel")], "t3") == 0.7
    assert learn.not_score(p, [q(1), q(2), q(3, "hotel")], "hotel") == 0.99


def test_not_score_ignores_questions_missing_from_answers():
    assert learn.not_score({}, [q(1)], "t3") == 0


def test_apply_not_scales_by_one_minus_not():
    assert learn.apply_not(0.8, 0) == 0.8
    assert learn.apply_not(0.8, 0.75) == pytest.approx(0.2)
    assert learn.apply_not(0.8, 1) == 0


def test_learn_tags_questions_with_the_dismissed_booking(monkeypatch):
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return [{"id": "Other Direction", "q": "Does it say only Manhattan-bound trains are affected?"},
                {"id": "other_dir", "q": "dup id gets a suffix?"},
                {"id": "wrong_stop", "q": "Are the skipped stops all east of Junction Blvd?"}]

    monkeypatch.setattr(learn, "_ask_hydrogen", fake)
    out = learn.learn({"event_id": "ev1", "booking_id": "t3"}, EVENT, IT)
    assert [x["group"] for x in out] == ["not"] * 3
    assert {x["booking_id"] for x in out} == {"t3"}
    assert len({x["id"] for x in out}) == 3
    assert all(x["id"].startswith("not__t3__") for x in out)
    assert "Manhattan-bound 7 skips 111 St" in seen["prompt"]
    assert "Does it mention the 7 train?" in seen["prompt"]
    assert "Flushing-bound" in seen["prompt"]


def test_learn_caps_at_five_questions(monkeypatch):
    monkeypatch.setattr(learn, "_ask_hydrogen", lambda p: [{"id": f"q{i}", "q": f"q{i}?"} for i in range(9)])
    assert len(learn.learn({"event_id": "ev1", "booking_id": "t3"}, EVENT, IT)) == 5


def test_learn_rejects_unknown_booking():
    with pytest.raises(KeyError):
        learn.learn({"event_id": "ev1", "booking_id": "nope"}, EVENT, IT)
