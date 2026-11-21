"""Real-data eval: every MTA subway alert active at run time, scored against the 3 test trips by the full Overheard
policy (Decision 1 fingerprint, Carbon on 0.4 to 0.8) and by a Hydrogen text baseline. The alert snapshot and labels
are saved in data/real/. Labels follow the data/spec.py rule and were assigned by the build agent (see LABEL_RULES)."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from overheard import config, alert, mta
from overheard.decide import score
from overheard.fingerprint import build_fingerprint
from overheard.gemini import ROOT
sys.argv = sys.argv[:1]
from eval.run_eval import text_relevance, keyword  # noqa: E402

TRIPS = json.loads((ROOT / "data/trips.json").read_text())
FPS = {k: build_fingerprint(t) for k, t in TRIPS.items()}
snap = ROOT / "data/real/mta_alerts_snapshot.json"
if snap.exists():
    alerts = json.loads(snap.read_text())
else:
    alerts = mta.fetch_alerts()
    snap.write_text(json.dumps(alerts, indent=1))

# Hand labels: (trip, substring of header) pairs that affect the trip under the data/spec.py rule.
LABEL_RULES = [("T2", "Uptown [A][C][F] trains are running with delays"),   # F northbound in Manhattan
               ("T3", "Flushing-bound [7] skips 52 St and 69 St")]           # stops between Grand Central and Flushing
labels = {(k, a["id"]): any(k == t and s in a["header"] for t, s in LABEL_RULES) for a in alerts for k in TRIPS}


def run(job):
    a, k = job
    text = mta.as_text(a)
    t0 = time.time()
    s = score([{"type": "text", "text": text}], TRIPS[k], FPS[k], label=f"mta {a['id']}/{k}")
    lat = time.time() - t0
    car = None
    if config.CONFLICT_AT <= s["relevance"] < config.ALERT_AT:
        car = alert.carbon_band(text.encode(), "text/plain", TRIPS[k], s)["relevant"]
    base, _ = text_relevance(text, k, f"mta {a['id']}")
    return {"id": a["id"], "trip": k, "routes": a["routes"], "header": a["header"][:160], "truth": labels[(k, a["id"])],
            "relevance": s["relevance"], "carbon": car, "policy": s["relevance"] >= config.ALERT_AT or bool(car),
            "text_baseline": base, "keyword": keyword(text, k), "latency": round(lat, 3)}


with ThreadPoolExecutor(4) as ex:
    rows = list(ex.map(run, [(a, k) for a in alerts for k in TRIPS]))
summ = {}
for key in ("policy", "text_baseline", "keyword"):
    tp = sum(r[key] and r["truth"] for r in rows); fp = sum(r[key] and not r["truth"] for r in rows)
    fn = sum(not r[key] and r["truth"] for r in rows)
    summ[key] = {"tp": tp, "fp": fp, "fn": fn}
summ["pairs"] = len(rows); summ["alerts"] = len(alerts); summ["positives"] = sum(r["truth"] for r in rows)
summ["sent_to_carbon"] = sum(r["carbon"] is not None for r in rows)
summ["decision_latency_median"] = sorted(r["latency"] for r in rows)[len(rows) // 2]
(ROOT / "eval/results/mta_real.json").write_text(json.dumps({"summary": summ, "rows": rows}, indent=1, ensure_ascii=False))
print(json.dumps(summ, indent=1))
for r in rows:
    if r["policy"] != r["truth"] or r["text_baseline"] != r["truth"]:
        print(r["trip"], r["truth"], "policy", r["policy"], r["relevance"], "base", r["text_baseline"], "|", r["header"][:100])
