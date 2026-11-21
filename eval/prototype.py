"""M1 prototype: Decision 1 on 3 announcement clips and 3 poster photos against 3 trips; latency and accuracy."""
import sys, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from overheard.decide import score_file
from overheard.fingerprint import build_fingerprint

trips = json.load(open("data/trips.json"))
fps = {k: build_fingerprint(t) for k, t in trips.items()}
labels = {i["id"]: i for i in json.load(open("data/labels.json"))["items"]}
items = ["a01", "a04", "a17", "i01", "i07", "i04"]
jobs = [(i, k) for i in items for k in trips]


def run(job):
    i, k = job
    r = score_file(labels[i]["file"], trips[k], fps[k])
    return i, k, r

t0 = time.time()
with ThreadPoolExecutor(3) as ex:
    res = list(ex.map(run, jobs))
rows = []
for i, k, r in res:
    truth = k in labels[i]["relevant"]
    pred = r["relevance"] >= 0.5
    rows.append({"item": i, "trip": k, "truth": truth, "relevance": r["relevance"], "direct": r["direct"],
                 "fp": r["fingerprint"], "ok": truth == pred, "latency": r["latency_s"], "nq": r["n_questions"],
                 "change": r["change_type"]})
    print(f"{i} {k} truth={truth!s:5} rel={r['relevance']:.2f} direct={r['direct']:.2f} fp={r['fingerprint']:.2f} "
          f"{r['change_type']:9} {r['latency_s']:.2f}s nq={r['n_questions']} {'OK' if truth == pred else 'MISS'}")
acc = sum(r["ok"] for r in rows) / len(rows)
lat = sorted(r["latency"] for r in rows)
print(f"accuracy {acc:.2f} ({sum(r['ok'] for r in rows)}/{len(rows)}), latency median {lat[len(lat)//2]:.2f}s max {lat[-1]:.2f}s, wall {time.time()-t0:.1f}s")
json.dump(rows, open("eval/prototype_results.json", "w"), indent=1)
