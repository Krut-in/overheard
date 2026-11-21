"""Ticket G: abroad evals. Scores rehearsal audio, rehearsal signs and radar news against the demo itinerary with
four methods (Decision 1 alone, full policy with Carbon, keyword baseline, Hydrogen transcribe then judge), runs a
held-out learning test, saves results under eval/results/abroad_*.json and draws eval/charts/abroad_summary.png.

Usage: .venv/bin/python eval/abroad_eval.py all      (verdicts are cached; delete eval/results/abroad_cache_*.json to redo)
"""
import base64, json, statistics, sys, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from google.genai import types
from overheard import config, learn
from overheard.alert import _json
from overheard.decide import shrink
from overheard.gemini import ROOT
from overheard.itinerary import load, fingerprint
from overheard.match import score

RES = ROOT / "eval" / "results"
CHART = ROOT / "eval" / "charts" / "abroad_summary.png"
REH = ROOT / "data" / "abroad" / "rehearsal"
IT = load(ROOT / "data" / "abroad" / "itinerary.json")
BIDS = [b["id"] for b in IT["bookings"]]
DECISION_PARALLEL = 3
SOURCES = ("rehearsal audio", "rehearsal signs", "radar news")
METHODS = ("decision", "policy", "keyword", "hydrogen")
LOW = types.ThinkingConfig(thinking_level="low")


# ---------- data ----------
def items() -> list[dict]:
    """Every eval item: {id, source, inp (match.score Input), text (script or news text), truth: [booking ids]}."""
    out = []
    for r in json.loads((REH / "items.json").read_text()):
        mime = "audio/mpeg" if r["kind"] == "audio" else "image/jpeg"
        inp = {"id": r["id"], "kind": r["kind"], "origin": "rehearsal", "mime": mime,
               "data_b64": base64.b64encode((REH / r["media"]).read_bytes()).decode()}
        out.append({"id": r["id"], "source": "rehearsal audio" if r["kind"] == "audio" else "rehearsal signs",
                    "inp": inp, "text": r["script"], "truth": [b for b, v in r["labels"].items() if v],
                    "lang": r["lang"]})
    labels = {i["id"]: i for i in json.loads((ROOT / "eval" / "abroad_labels.json").read_text())["items"]}
    snap = json.loads((ROOT / "data" / "abroad" / "radar" / "snapshot_2026-11-21.json").read_text())
    for x in snap["items"]:
        out.append({"id": x["id"], "source": "radar news", "inp": x, "text": x["text"],
                    "truth": [b for b, v in labels[x["id"]]["labels"].items() if v], "lang": x["lang"]})
    return out


def media(it: dict) -> tuple[bytes, str]:
    inp = it["inp"]
    if "data_b64" in inp:
        return shrink(base64.b64decode(inp["data_b64"]), inp["mime"])
    return it["text"].encode(), "text/plain"


def part(it: dict):
    data, mime = media(it)
    return "Input text: " + data.decode() if mime == "text/plain" else types.Part.from_bytes(data=data, mime_type=mime)


def cached(name: str, keys: list[str], fn, workers: int) -> dict:
    """Run fn(key) for keys missing from eval/results/abroad_cache_<name>.json, save, return the full dict."""
    path = RES / f"abroad_cache_{name}.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    todo = [k for k in keys if k not in cache]
    if todo:
        print(f"[{name}] {len(todo)} new calls ({len(cache)} cached)", flush=True)
        with ThreadPoolExecutor(workers) as ex:
            for k, v in zip(todo, ex.map(fn, todo)):
                cache[k] = v
                path.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    return cache


def bookings_text() -> str:
    return "\n".join(f"- {b['id']}: {b['title']}, {b['start']} to {b['end']}, from {b['from_place']}"
                     f"{', to ' + b['to_place'] if b['to_place'] else ''}. {b['details']}" for b in IT["bookings"])


RULE = ("An input matters to a booking only when it directly changes that booking's service, gate, entrance, "
        "station or stop on its dates. Other flights, trains or lines, other dates, normal service and knock-on "
        "effects from another booking do not count.")


# ---------- methods ----------
def run_decision(all_items, fp, learned=None, name="decision") -> dict:
    by = {i["id"]: i for i in all_items}

    def one(k):
        v = score(by[k]["inp"], IT, fp, learned or [])
        return {k2: v[k2] for k2 in ("relevance", "booking_id", "per_booking", "change_type", "top_hits", "route",
                                     "latency_s")}
    return cached(name, list(by), one, DECISION_PARALLEL)


CARBON_SCHEMA = {"type": "object", "properties": {
    "relevant": {"type": "boolean"}, "booking_id": {"type": "string", "enum": [*BIDS, "none"]},
    "reason": {"type": "string", "description": "one sentence"}}, "required": ["relevant", "booking_id", "reason"]}


def run_carbon(all_items, dec) -> dict:
    by = {i["id"]: i for i in all_items}
    band = [k for k in by if config.CONFLICT_AT <= dec[k]["relevance"] < config.ALERT_AT]

    def one(k):
        v = dec[k]
        prompt = (f"A traveller's bookings:\n{bookings_text()}\n{RULE}\nA fast relevance model was unsure "
                  f"(relevance {v['relevance']}, nearest booking {v['booking_id']}, strongest signals: "
                  f"{json.dumps(v['top_hits'][:3], ensure_ascii=False)}). Look at the input itself. Does it directly "
                  "change one of these bookings? Name the booking, or none.")
        t0 = time.time()
        r = _json(config.CARBON, f"abroad band check {k}", [prompt, part(by[k])], CARBON_SCHEMA)
        return dict(r, latency_s=round(time.time() - t0, 3))
    return cached("carbon", band, one, 6)


# Keyword baseline: a booking string (operator, number or place) plus a disruption word, on the transcript or text.
# It reads the ground-truth script for audio and signs, which is generous to the baseline.
KEYS = {"flight_out": ["air france", "af 23", "af23", "terminal 2e", "2e"],
        "hotel_paris": ["saint-paul", "saint paul", "chemin vert", "rue de turenne", "marais"],
        "museum_louvre": ["louvre", "pyramide", "pyramid", "palais-royal"],
        "train_ams": ["eurostar", "9315", "gare du nord"],
        "hotel_ams": ["westermarkt", "tram 13", "tram 17", "lijn 13", "lijn 17", "prinsengracht"],
        "flight_home": ["klm", "kl 641", "kl641", "schiphol"]}
DISRUPT = ["cancel", "annul", "delay", "retard", "vertrag", "strike", "grève", "greve", "staking", "closed", "ferm",
           "gesloten", "suppr", "perturb", "storing", "disrupt", "divert", "omleid", "omgeleid", "werkzaamheden",
           "travaux", "works", "change", "changement", "gewijzigd", "wijziging", "aangepast", "moved", "déplac",
           "no trams", "geen tram", "geen trein", "not running", "rijdt niet", "rijden niet", "gate", "porte", "quai",
           "spoor", "platform", "belt", "tapis", "blocked", "bloqu", "interrompu"]


def fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def run_keyword(it: dict) -> dict:
    t = fold(it["text"])
    if not any(fold(w) in t for w in DISRUPT):
        return {"alert": False, "booking_id": None}
    hit = [b for b in BIDS if any(fold(k) in t for k in KEYS[b])]
    return {"alert": bool(hit), "booking_id": hit[0] if hit else None}


HYD_SCHEMA = {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "object", "properties": {
    "booking_id": {"type": "string", "enum": BIDS}, "relevant": {"type": "boolean"}},
    "required": ["booking_id", "relevant"]}}}, "required": ["answers"]}


def run_hydrogen(all_items) -> dict:
    """Hydrogen transcribes or reads the input (media only), then one text call answers yes or no per booking."""
    by = {i["id"]: i for i in all_items}

    def one(k):
        it = by[k]
        t0 = time.time()
        text = it["text"]
        if it["source"] != "radar news":
            text = _json(config.HYDROGEN, f"abroad transcribe {k}", [
                "Transcribe the speech, or copy every line of text in this image, in its original language.",
                part(it)], {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                LOW)["text"]
        t1 = time.time()
        prompt = (f"A traveller's bookings:\n{bookings_text()}\n{RULE}\nInput:\n{text}\n"
                  "For each booking, answer whether this input directly changes it.")
        r = _json(config.HYDROGEN, f"abroad judge {k}", [prompt], HYD_SCHEMA, LOW)
        yes = [a["booking_id"] for a in r["answers"] if a["relevant"]]
        return {"text": text, "yes": yes, "transcribe_s": round(t1 - t0, 3), "latency_s": round(time.time() - t0, 3)}
    return cached("hydrogen", list(by), one, 8)


# ---------- scoring ----------
def outcomes(all_items, dec, carb, hyd) -> dict:
    """Per item and method: {alert, booking_id, latency_s}."""
    out = {}
    for it in all_items:
        k, v = it["id"], dec[it["id"]]
        o = {"decision": {"alert": v["relevance"] >= config.ALERT_AT, "booking_id": v["booking_id"],
                          "latency_s": v["latency_s"]}}
        if k in carb:
            c = carb[k]
            o["policy"] = {"alert": c["relevant"] and c["booking_id"] != "none",
                           "booking_id": c["booking_id"] if c["booking_id"] != "none" else v["booking_id"],
                           "latency_s": round(v["latency_s"] + c["latency_s"], 3), "carbon": True}
        else:
            o["policy"] = dict(o["decision"], carbon=False)
        t0 = time.perf_counter()
        o["keyword"] = dict(run_keyword(it), latency_s=round(time.perf_counter() - t0, 6))
        h = hyd[k]
        o["hydrogen"] = {"alert": bool(h["yes"]), "booking_id": h["yes"][0] if h["yes"] else None,
                         "latency_s": h["latency_s"], "all_yes": h["yes"]}
        out[k] = o
    return out


def table(all_items, outs) -> dict:
    res = {}
    for src in SOURCES:
        rs = [i for i in all_items if i["source"] == src]
        rel = [i for i in rs if i["truth"]]
        res[src] = {"items": len(rs), "relevant": len(rel)}
        for m in METHODS:
            o = [(i, outs[i["id"]][m]) for i in rs]
            caught = [i for i, x in o if i["truth"] and x["alert"]]
            res[src][m] = {
                "caught": len(caught), "false_alerts": sum(1 for i, x in o if not i["truth"] and x["alert"]),
                "right_booking": sum(1 for i, x in o if i["truth"] and x["alert"] and x["booking_id"] in i["truth"]),
                "median_latency_s": round(statistics.median(x["latency_s"] for _, x in o), 3)}
            if m == "policy":
                res[src][m]["sent_to_carbon"] = sum(1 for _, x in o if x.get("carbon"))
    return res


def print_table(res):
    print(f"\n{'source':16} {'method':9} {'caught':>9} {'false':>6} {'right bk':>9} {'median s':>9} {'carbon':>7}")
    for src in SOURCES:
        r = res[src]
        for m in METHODS:
            x = r[m]
            print(f"{src:16} {m:9} {x['caught']:>4} / {r['relevant']:<2} {x['false_alerts']:>4}/{r['items'] - r['relevant']:<2}"
                  f"{x['right_booking']:>7}   {x['median_latency_s']:>8.3f} {x.get('sent_to_carbon', ''):>7}")


# ---------- learning, held out ----------
def run_learning(all_items, dec, fp) -> dict:
    reh = sorted([i for i in all_items if i["source"] != "radar news"], key=lambda i: i["id"])
    near = [i for i in reh if not i["truth"]]
    half1, half2 = near[0::2], near[1::2]
    relevant = [i for i in reh if i["truth"]]
    path = RES / "abroad_learned.json"
    if path.exists():
        learned_log = json.loads(path.read_text())
    else:
        learned_log = {"dismissed": [], "questions": []}
        targets = [i for i in half1 if dec[i["id"]]["relevance"] >= config.CONFLICT_AT and dec[i["id"]]["booking_id"]]

        def one(i):
            v = dec[i["id"]]
            qs = learn.learn({"booking_id": v["booking_id"]},
                             {"input": {"id": i["id"], "kind": i["inp"]["kind"], "text": i["text"]}, "verdict": v}, IT)
            return {"id": i["id"], "booking_id": v["booking_id"], "relevance": v["relevance"],
                    "questions": qs}
        with ThreadPoolExecutor(2) as ex:
            for d in ex.map(one, targets):
                learned_log["dismissed"].append({k: d[k] for k in ("id", "booking_id", "relevance")})
                for q in d["questions"]:
                    if q["id"] not in {x["id"] for x in learned_log["questions"]}:
                        learned_log["questions"].append(q)
        path.write_text(json.dumps(learned_log, indent=1, ensure_ascii=False))
    learned = [{k: q[k] for k in ("id", "booking_id", "group", "q")} for q in learned_log["questions"]]
    rescore = half2 + relevant
    after = run_decision(rescore, fp, learned, name="decision_learned") if learned else {
        i["id"]: dec[i["id"]] for i in rescore}

    def fa(rows, d):
        return sum(1 for i in rows if d[i["id"]]["relevance"] >= config.ALERT_AT)

    def band(rows, d):
        return sum(1 for i in rows if config.CONFLICT_AT <= d[i["id"]]["relevance"] < config.ALERT_AT)
    fell = [{"id": i["id"], "before": dec[i["id"]]["relevance"], "after": after[i["id"]]["relevance"]}
            for i in relevant if dec[i["id"]]["relevance"] >= config.ALERT_AT > after[i["id"]]["relevance"]]
    return {"half1": [i["id"] for i in half1], "half2": [i["id"] for i in half2],
            "dismissed": learned_log["dismissed"], "n_learned": len(learned),
            "half2_false_alerts_before": fa(half2, dec), "half2_false_alerts_after": fa(half2, after),
            "half2_band_before": band(half2, dec), "half2_band_after": band(half2, after),
            "relevant_alerting_before": fa(relevant, dec), "relevant_alerting_after": fa(relevant, after),
            "relevant_fell_below_0.8": fell,
            "rows": [{"id": i["id"], "truth": i["truth"], "before": dec[i["id"]]["relevance"],
                      "after": after[i["id"]]["relevance"]} for i in rescore]}


# ---------- chart ----------
def chart(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = {"decision": "Decision 1 at 0.8", "policy": "Policy + Carbon", "keyword": "Keyword baseline",
             "hydrogen": "Hydrogen transcribe + judge"}
    colors = {"decision": "#2f6fdf", "policy": "#1a9e77", "keyword": "#9a9a9a", "hydrogen": "#d9822b"}
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=False)
    for ax, src in zip(axes, SOURCES):
        r = res[src]
        x = range(len(METHODS))
        w = 0.38
        ax.bar([i - w / 2 for i in x], [r[m]["caught"] for m in METHODS], w, color=[colors[m] for m in METHODS])
        ax.bar([i + w / 2 for i in x], [r[m]["false_alerts"] for m in METHODS], w, color="white",
               edgecolor=[colors[m] for m in METHODS], hatch="//")
        for i, m in enumerate(METHODS):
            ax.text(i - w / 2, r[m]["caught"] + 0.1, str(r[m]["caught"]), ha="center", fontsize=8)
            ax.text(i + w / 2, r[m]["false_alerts"] + 0.1, str(r[m]["false_alerts"]), ha="center", fontsize=8)
        ax.set_xticks(list(x), [names[m].replace(" + ", "\n+ ").replace(" at", "\nat").replace(" baseline", "\nbaseline")
                                for m in METHODS], fontsize=7)
        ax.set_title(f"{src}: {r['relevant']} relevant, {r['items'] - r['relevant']} not", fontsize=9)
        ax.axhline(r["relevant"], color="#444", lw=0.6, ls=":")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("items (solid: caught, hatched: false alerts)", fontsize=8)
    fig.suptitle("Overheard abroad: caught and false alerts per method (dotted line = all relevant items)", fontsize=10)
    fig.tight_layout()
    CHART.parent.mkdir(exist_ok=True)
    fig.savefig(CHART, dpi=150)


def main():
    t0 = time.time()
    all_items = items()
    fp = fingerprint(IT)
    print(f"{len(all_items)} items, {len(fp)} fingerprint questions")
    dec = run_decision(all_items, fp)
    carb = run_carbon(all_items, dec)
    hyd = run_hydrogen(all_items)
    outs = outcomes(all_items, dec, carb, hyd)
    res = table(all_items, outs)
    print_table(res)
    lrn = run_learning(all_items, dec, fp)
    print(f"\nLearning, held out: dismissed {len(lrn['dismissed'])} half-1 near misses once each, "
          f"{lrn['n_learned']} not-questions kept")
    print(f"  half 2 near misses ({len(lrn['half2'])}): false alerts {lrn['half2_false_alerts_before']} -> "
          f"{lrn['half2_false_alerts_after']}, Carbon band {lrn['half2_band_before']} -> {lrn['half2_band_after']}")
    print(f"  relevant rehearsal items alerting at 0.8: {lrn['relevant_alerting_before']} -> "
          f"{lrn['relevant_alerting_after']}; fell below 0.8: {lrn['relevant_fell_below_0.8'] or 'none'}")
    lat = [dec[i["id"]]["latency_s"] for i in all_items]
    print(f"\nDecision 1 median latency over {len(lat)} calls: {statistics.median(lat):.2f} s "
          f"(audio {statistics.median(dec[i['id']]['latency_s'] for i in all_items if i['source'] == 'rehearsal audio'):.2f}, "
          f"signs {statistics.median(dec[i['id']]['latency_s'] for i in all_items if i['source'] == 'rehearsal signs'):.2f}, "
          f"news {statistics.median(dec[i['id']]['latency_s'] for i in all_items if i['source'] == 'radar news'):.2f})")
    misses = []
    for i in all_items:
        for m in METHODS:
            o = outs[i["id"]][m]
            if bool(i["truth"]) != o["alert"] or (o["alert"] and i["truth"] and o["booking_id"] not in i["truth"]):
                misses.append({"id": i["id"], "source": i["source"], "method": m, "truth": i["truth"],
                               "alert": o["alert"], "booking_id": o["booking_id"],
                               "relevance": dec[i["id"]]["relevance"],
                               "carbon_reason": carb.get(i["id"], {}).get("reason")})
    print(f"\nWrong calls ({len(misses)} item-method pairs) for Decision and policy:")
    for x in misses:
        if x["method"] in ("decision", "policy"):
            print(f"  {x['method']:8} {x['id']:18} truth={x['truth'] or '-'} alert={x['alert']} "
                  f"booking={x['booking_id']} rel={x['relevance']:.3f} {(x['carbon_reason'] or '')[:90]}")
    rows = [{"id": i["id"], "source": i["source"], "lang": i["lang"], "truth": i["truth"],
             "decision": dec[i["id"]], "carbon": carb.get(i["id"]), "outcomes": outs[i["id"]],
             "hydrogen_text": hyd[i["id"]]["text"][:400]} for i in all_items]
    (RES / "abroad_rows.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    (RES / "abroad_summary.json").write_text(json.dumps(
        {"per_source": res, "learning": {k: v for k, v in lrn.items() if k != "rows"},
         "decision_median_latency_s": round(statistics.median(lat), 3), "wrong_calls": misses}, indent=1,
        ensure_ascii=False))
    (RES / "abroad_learning.json").write_text(json.dumps(lrn, indent=1, ensure_ascii=False))
    chart(res)
    print(f"\nSaved eval/results/abroad_summary.json, abroad_rows.json, abroad_learning.json, chart {CHART.name}"
          f" ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    if sys.argv[1:] != ["all"]:
        sys.exit(__doc__)
    main()
