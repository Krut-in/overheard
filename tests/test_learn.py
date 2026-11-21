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


def test_not_score_is_gated_max_over_that_bookings_questions_only():
    p = {q(1)["id"]: 0.2, q(2)["id"]: 0.7, q(3, "hotel")["id"]: 0.99}
    assert learn.not_score(p, [q(1), q(2), q(3, "hotel")], "t3") == pytest.approx(0.4)
    assert learn.not_score(p, [q(1), q(2), q(3, "hotel")], "hotel") == pytest.approx(0.98)


def test_not_gate_ignores_noise_and_keeps_strong_answers():
    assert learn.not_effective(0.0) == 0
    assert learn.not_effective(0.22) == 0
    assert learn.not_effective(0.5) == 0
    assert learn.not_effective(0.75) == pytest.approx(0.5)
    assert learn.not_effective(1.0) == pytest.approx(1.0)


def test_not_score_ignores_questions_missing_from_answers():
    assert learn.not_score({}, [q(1)], "t3") == 0


def test_apply_not_scales_by_one_minus_not():
    assert learn.apply_not(0.8, 0) == 0.8
    assert learn.apply_not(0.8, 0.75) == pytest.approx(0.2)
    assert learn.apply_not(0.8, 1) == 0


def stub(monkeypatch, questions, keep=("Flushing-bound 7 skips Queensboro Plaza.",), probs=None):
    """Stub Hydrogen (candidates plus keep examples) and the Decision guard (probabilities per keep example)."""
    seen = {}

    def fake_hydrogen(prompt):
        seen["prompt"] = prompt
        return {"questions": questions, "keep_examples": list(keep)}

    def fake_check(qs, examples):
        seen["examples"] = examples
        return [{q["id"]: (probs or {}).get(q["q"], 0.0) for q in qs} for _ in examples]

    monkeypatch.setattr(learn, "_ask_hydrogen", fake_hydrogen)
    monkeypatch.setattr(learn, "_check", fake_check)
    return seen


def test_learn_tags_questions_with_the_dismissed_booking(monkeypatch):
    seen = stub(monkeypatch, [{"id": "Other Direction", "q": "Only Manhattan-bound trains affected?"},
                              {"id": "other direction", "q": "Same id after slugging?"},
                              {"id": "wrong_stop", "q": "Are the skipped stops all east of Junction Blvd?"}])
    assert learn.GUARD_MAX == 0.1
    out = learn.learn({"event_id": "ev1", "booking_id": "t3"}, EVENT, IT)
    assert [x["group"] for x in out] == ["not"] * 3
    assert {x["booking_id"] for x in out} == {"t3"}
    assert len({x["id"] for x in out}) == 3
    assert all(x["id"].startswith("not__t3__") for x in out)
    assert "Manhattan-bound 7 skips 111 St" in seen["prompt"]
    assert "Does it mention the 7 train?" in seen["prompt"]
    assert "Flushing-bound" in seen["prompt"]


def test_learn_drops_questions_that_fire_on_a_true_alert(monkeypatch):
    seen = stub(monkeypatch, [{"id": "a", "q": "good?"}, {"id": "b", "q": "fires on true alert?"},
                              {"id": "c", "q": "also good?"}],
                probs={"fires on true alert?": learn.GUARD_MAX + 0.01})
    out = learn.learn({"event_id": "ev1", "booking_id": "t3"}, EVENT, IT)
    assert [x["q"] for x in out] == ["good?", "also good?"]
    assert seen["examples"] == ["Flushing-bound 7 skips Queensboro Plaza."]
    assert out[0]["guard_max"] == 0.0


def test_learn_caps_at_three_questions(monkeypatch):
    stub(monkeypatch, [{"id": f"q{i}", "q": f"q{i}?"} for i in range(9)])
    assert len(learn.learn({"event_id": "ev1", "booking_id": "t3"}, EVENT, IT)) == 3


def test_learn_rejects_unknown_booking():
    with pytest.raises(KeyError):
        learn.learn({"event_id": "ev1", "booking_id": "nope"}, EVENT, IT)
