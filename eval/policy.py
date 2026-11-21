"""Full Overheard policy on the main eval rows: alert at 0.8, Carbon decides the 0.4 to 0.8 band, silence below."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from overheard import config, alert
from overheard.decide import shrink, MIME
from overheard.gemini import ROOT

rows = json.loads((ROOT / "eval/results/main_rows.json").read_text())
trips = json.loads((ROOT / "data/trips.json").read_text())
files = {i["id"]: i["file"] for i in json.loads((ROOT / "data/labels.json").read_text())["items"]}
files["7_train_service_change_notice_4_languages"] = "data/real/images/7_train_service_change_notice_4_languages.jpg"
for r in rows:
    r["relevance"] = round(config.DIRECT_WEIGHT * r["direct"] + (1 - config.DIRECT_WEIGHT) * r["fp"], 3)


def carbon(r):
    p = ROOT / files.get(r["id"], f"data/real/images/{r['id']}.jpg")
    data, mime = shrink(p.read_bytes(), MIME[p.suffix.lower()])
    t0 = time.time()
    v = alert.carbon_band(data, mime, trips[r["trip"]], {"relevance": r["relevance"], "top_hits": []})
    return v["relevant"], time.time() - t0, v["reason"]


band = [r for r in rows if config.CONFLICT_AT <= r["relevance"] < config.ALERT_AT]
with ThreadPoolExecutor(6) as ex:
    for r, (rel, dt, why) in zip(band, ex.map(carbon, band)):
        r["carbon"], r["carbon_latency"], r["carbon_reason"] = rel, round(dt, 2), why
for r in rows:
    r["policy"] = r["relevance"] >= config.ALERT_AT or bool(r.get("carbon"))
out = {}
for mod in ("audio", "image"):
    rs = [r for r in rows if r["modality"] == mod]
    tp = sum(r["policy"] and r["truth"] for r in rs); fp = sum(r["policy"] and not r["truth"] for r in rs)
    fn = sum(not r["policy"] and r["truth"] for r in rs)
    b = [r for r in rs if "carbon" in r]
    out[mod] = {"pairs": len(rs), "tp": tp, "fp": fp, "fn": fn, "precision": round(tp / max(1, tp + fp), 3),
                "recall": round(tp / max(1, tp + fn), 3), "band_sent_to_carbon": len(b),
                "carbon_said_relevant": sum(r["carbon"] for r in b),
                "carbon_latency_median": sorted(r["carbon_latency"] for r in b)[len(b) // 2] if b else None,
                "silence_receipts": sum(not r["policy"] for r in rs)}
(ROOT / "eval/results/policy_rows.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
(ROOT / "eval/results/policy_summary.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
for r in rows:
    if r["policy"] != r["truth"]:
        print("MISS", r["id"], r["trip"], r["truth"], r["relevance"], r.get("carbon_reason"))
