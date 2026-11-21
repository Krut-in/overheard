"""Learning eval on real MTA data: the 7 train trip (T3, Grand Central to Flushing-Main St) acts as one pseudo-booking.
The real false alert ("Manhattan-bound 7 skips 111 St...") is dismissed once, Hydrogen writes `not` questions, and every
alert in the MTA snapshot is scored with the cached fingerprint plus those questions in one Decision call each.
before = subway relevance from that call, after = before x (1 - not). Writes eval/results/learn.json."""
import json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from overheard import config, decide, learn, mta
from overheard.fingerprint import build_fingerprint
from overheard.gemini import ROOT

TRIP_ID = "T3"
IT_ID = "subway_T3"
FALSE_ALERT = "Manhattan-bound [7] skips 111 St"
TRUE_ALERT = "Flushing-bound [7] skips 52 St and 69 St"

# Held-out notices written by the build agent, never shown to Hydrogen. truth = affects the Flushing-bound 7 trip.
# They are reported but do not gate the checks: the ticket's pass rule is on the real MTA snapshot.
HELD_OUT = [
    ("held_wrong_dir_delay", False, "MTA service alert. Manhattan-bound [7] trains are running with delays near "
     "Queensboro Plaza while we address a signal problem. Flushing-bound [7] trains are running on schedule."),
    ("held_wrong_dir_suspended", False, "MTA service alert. No Manhattan-bound [7] between 74 St-Broadway and "
     "Queensboro Plaza. Take the Flushing-bound [7] to 74 St-Broadway and transfer."),
    ("held_right_dir_delay", True, "MTA service alert. Flushing-bound [7] trains are running with delays near "
     "Queensboro Plaza while we address a signal problem. Manhattan-bound [7] trains are running on schedule."),
    ("held_both_dirs", True, "MTA service alert. [7] trains are running with delays in both directions between "
     "Court Sq and 61 St-Woodside while we remove a disabled train."),
]

trip = json.loads((ROOT / "data/trips.json").read_text())[TRIP_ID]
fp = build_fingerprint(trip)  # cached in data/fingerprints/
alerts = json.loads((ROOT / "data/real/mta_alerts_snapshot.json").read_text())
booking = {"id": TRIP_ID, "kind": "train", "title": trip["summary"], "operator": "MTA New York City Subway",
           "number": trip["line"], "from_place": trip["board"], "to_place": trip["alight"],
           "details": f"{trip['line']} train {trip['direction']}; stops on the way: {', '.join(trip['stops_between'])}",
           "start": "", "end": "", "city": "New York", "country": "US", "langs": ["en"]}
it = {"id": IT_ID, "bookings": [booking]}

# capture the raw Decision answers so each learned question's probability can be reported
_raw = {}


class _Capture:
    def __init__(self, real):
        self.real, self.decisions = real, self

    def create(self, **kw):
        r = self.real.decisions.create(**kw)
        _raw[threading.get_ident()] = r.answers
        return r


_real_client = decide.client
decide.client = lambda: _Capture(_real_client())


def run(a, learned):
    text = a.get("text") or mta.as_text(a)
    s = decide.score([{"type": "text", "text": text}], trip, fp + learned, label=f"learn {a['id']}")
    ans = _raw[threading.get_ident()]
    p = {q["id"]: round(ans[q["id"]].noul, 3) for q in learned if q["id"] in ans}
    nb = learn.not_score(p, learned, TRIP_ID)
    return {"id": a["id"], "routes": a["routes"], "header": a["header"][:160], "before": s["relevance"],
            "not": round(nb, 3), "after": round(learn.apply_not(s["relevance"], nb), 3), "not_p": p,
            "latency_s": s["latency_s"]}


def band(x):
    return "alert" if x >= config.ALERT_AT else "carbon" if x >= config.CONFLICT_AT else "silence"


t_start = time.time()
false_a = next(a for a in alerts if FALSE_ALERT in a["header"])
true_a = next(a for a in alerts if TRUE_ALERT in a["header"])

# 1. the false alert as the traveller saw it (no learned questions yet)
first = decide.score([{"type": "text", "text": mta.as_text(false_a)}], trip, fp, label="learn dismissed input")
event = {"id": "ev_false", "input": {"id": false_a["id"], "kind": "text", "text": mta.as_text(false_a)},
         "verdict": {"relevance": first["relevance"],
                     "top_hits": [dict(h, booking_id=TRIP_ID) for h in first["top_hits"]]}}

# 2. one dismissal -> learned questions
learned = learn.learn({"event_id": "ev_false", "booking_id": TRIP_ID}, event, it)
learn.save_learned(IT_ID, learned)

# 3. every alert in the snapshot, fingerprint + learned questions, one Decision call each
with ThreadPoolExecutor(4) as ex:
    rows = list(ex.map(lambda a: run(a, learned), alerts))
    held = list(ex.map(lambda h: dict(run({"id": h[0], "routes": ["7"], "header": h[2][20:180], "text": h[2]},
                                          learned), truth=h[1]), HELD_OUT))
by_id = {r["id"]: r for r in rows}
fr, tr = by_id[false_a["id"]], by_id[true_a["id"]]
others = [r for r in rows if r["id"] not in (false_a["id"], true_a["id"])]
risen = [r for r in others if r["after"] >= config.ALERT_AT]

checks = {"false_after_under_0.4": fr["after"] < 0.4, "true_after_at_least_0.8": tr["after"] >= 0.8,
          "no_other_alert_in_alert_band": not risen}
out = {"trip": TRIP_ID, "itinerary_id": IT_ID, "dismissed": false_a["id"],
       "dismissed_relevance_when_shown": first["relevance"], "learned": learned,
       "keep_examples": learn.LAST.get("keep_examples", []), "dropped": learn.LAST.get("dropped", []),
       "false_alert": fr, "true_alert": tr, "others": sorted(others, key=lambda r: -r["before"]), "held_out": held,
       "checks": checks, "passed": all(checks.values()), "wall_s": round(time.time() - t_start, 1)}
(ROOT / "eval/results/learn.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))

print("\nKeep examples Hydrogen wrote (true alerts for T3, used by the guard):")
for e in out["keep_examples"]:
    print(f"  - {e}")
print("Dropped by the guard (fired on a keep example):")
for q in out["dropped"]:
    print(f"  {q['guard_max']:.2f}  {q['q']}")
print("Learned questions kept (booking T3), with max p on the keep examples:")
for q in learned:
    print(f"  {q['guard_max']:.2f}  {q['id']}: {q['q']}")
print(f"\nDismissed alert scored {first['relevance']} when shown.\n")
print(f"{'':6} {'before':>6} {'not':>5} {'after':>6}  band after  header")
for tag, r in [("FALSE", fr), ("TRUE", tr)] + [("other", r) for r in out["others"]]:
    print(f"{tag:6} {r['before']:6.3f} {r['not']:5.2f} {r['after']:6.3f}  {band(r['after']):10}  {r['header'][:70]!r}")
print("\nHeld-out notices (hand-written, not shown to Hydrogen):")
for r in held:
    print(f"  truth={str(r['truth']):5} before {r['before']:.3f} ({band(r['before'])}) -> after {r['after']:.3f} "
          f"({band(r['after'])})  not={r['not']:.2f}  {r['id']}")
print("\nPer learned question, false alert vs true alert:")
for q in learned:
    print(f"  {fr['not_p'].get(q['id'], '-'):>5} {tr['not_p'].get(q['id'], '-'):>5}  {q['id']}")
print("\nchecks:", json.dumps(checks), "PASS" if out["passed"] else "FAIL")
