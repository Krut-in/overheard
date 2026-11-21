"""Accuracy of the extracted change: Neon extracts the change from each relevant (item, trip) pair, and
Decision 1 grades it against the ground-truth script on a 3-level score (wrong, partial, correct)."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from overheard import alert, config
from overheard.decide import shrink, MIME
from overheard.gemini import client, ROOT

trips = json.loads((ROOT / "data/trips.json").read_text())
items = [i for i in json.loads((ROOT / "data/labels.json").read_text())["items"] if i["modality"] in ("audio", "image")]
pairs = [(i, k) for i in items for k in i["relevant"]]


def run(p):
    it, k = p
    path = ROOT / it["file"]
    data, mime = shrink(path.read_bytes(), MIME[path.suffix.lower()])
    t0 = time.time()
    ch = alert.extract_change(data, mime, trips[k])
    lat = time.time() - t0
    g = client().decisions.create(model=config.DECISION, input=(
        f"Ground truth (what the {it['modality']} actually says): {it['text']}\n"
        f"Rider trip: {trips[k]['summary']}\nExtracted change: {ch['change']}\nSuggested action: {ch['action']}"),
        questions={"grade": {"type": "choice", "instructions": "How accurate is the extracted change and action compared with the ground truth?",
                             "criteria": {"wrong": "States a different change, wrong line or wrong stations, or invents facts.",
                                          "partial": "Right change but misses or blurs an important detail (a station, the alternative).",
                                          "correct": "States the change and a sensible action with no factual error."}}})
    a = g.answers["grade"]
    return {"id": it["id"], "trip": k, "modality": it["modality"], "grade": a.choice, "grade_p": round(a.confidence, 3),
"neon_latency": round(lat, 2), "change": ch["change"], "quote": ch["quote"]}


with ThreadPoolExecutor(5) as ex:
    rows = list(ex.map(run, pairs))
summary = {g: sum(r["grade"] == g for r in rows) for g in ("correct", "partial", "wrong")}
summary["n"] = len(rows)
summary["neon_latency_median"] = sorted(r["neon_latency"] for r in rows)[len(rows) // 2]
(ROOT / "eval/results/extraction.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False))
print(summary)
for r in rows:
    if r["grade"] != "correct":
        print(r["id"], r["trip"], r["grade"], r["change"])
