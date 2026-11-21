"""Eval harness: Overheard (Decision 1 fingerprint) against two baselines, per modality, plus noise and blur breaking points.

Baselines:  text  = Hydrogen transcribes/OCRs the input, then Hydrogen answers "is this relevant?" in text.
            keyword = the same transcript, relevant if it names the rider's line AND a disruption word.
Usage: .venv/bin/python eval/run_eval.py [main|noise|blur|video|all]
"""
import io, json, random, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from google.genai import types
from PIL import Image, ImageFilter, ImageEnhance
from overheard import config, alert
from overheard.decide import score_bytes, shrink, MIME
from overheard.fingerprint import build_fingerprint
from overheard.gemini import client, timed, ROOT
from overheard.video import sample_frames, segments

OUT = ROOT / "eval" / "results"; OUT.mkdir(parents=True, exist_ok=True)
CH = ROOT / "eval" / "charts"; CH.mkdir(parents=True, exist_ok=True)
TRIPS = json.loads((ROOT / "data" / "trips.json").read_text())
FPS = {k: build_fingerprint(t) for k, t in TRIPS.items()}
LABELS = json.loads((ROOT / "data" / "labels.json").read_text())["items"]
POOL = ThreadPoolExecutor(4)
DISRUPT = r"delay|retras|suspend|not running|no .{0,12}trains|no hay|skip|no paran|not stop|via|running on|reroute|express track|track \d|closed|cerrad|shuttle|end at|última parada|bypass"


def load(item) -> tuple[bytes, str]:
    p = ROOT / item["file"]
    return p.read_bytes(), MIME[p.suffix.lower()]


# ---------- Overheard ----------
def overheard(data, mime, trip_key, label):
    t0 = time.time()
    s = score_bytes(data, mime, TRIPS[trip_key], FPS[trip_key], label=label)
    return {"relevance": s["relevance"], "direct": s["direct"], "fp": s["fingerprint"], "latency": time.time() - t0}


# ---------- baselines ----------
def transcribe(data, mime, label):
    data, mime = shrink(data, mime)
    t0 = time.time()
    r = timed(config.HYDROGEN, f"baseline transcribe {label}", client().models.generate_content, model=config.HYDROGEN,
              contents=["Transcribe every word spoken or written in this input, verbatim, in its original language. "
                        "If there are no words, reply NONE.", types.Part.from_bytes(data=data, mime_type=mime)],
              config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="low")))
    return (r.text or "").strip(), time.time() - t0


def text_relevance(text, trip_key, label):
    t = TRIPS[trip_key]
    t0 = time.time()
    r = timed(config.HYDROGEN, f"baseline relevance {label}", client().models.generate_content, model=config.HYDROGEN,
              contents=[f"Rider trip: {t['summary']} (stops between: {', '.join(t['stops_between'])}). Text heard or seen "
                        f"at a station: \"{text}\". Does it announce a service change on the rider's line in their direction "
                        "between their stations, or at their boarding or alighting station? Answer yes or no."],
              config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="low"),
                                                 response_mime_type="application/json",
                                                 response_json_schema={"type": "object", "properties": {"relevant": {"type": "boolean"}}, "required": ["relevant"]}))
    return bool(json.loads(r.text)["relevant"]), time.time() - t0


def keyword(text, trip_key):
    line = TRIPS[trip_key]["line"]
    has_line = re.search(rf"(?<![A-Za-z0-9]){re.escape(line)}(?![A-Za-z0-9])", text) is not None
    return has_line and re.search(DISRUPT, text, re.I) is not None


def metrics(rows, key, thr=None):
    tp = fp = fn = tn = 0
    for r in rows:
        pred = r[key] >= thr if thr is not None else bool(r[key])
        if pred and r["truth"]: tp += 1
        elif pred: fp += 1
        elif r["truth"]: fn += 1
        else: tn += 1
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(prec, 3), "recall": round(rec, 3),
            "accuracy": round((tp + tn) / max(1, len(rows)), 3)}


def run_pairs(pairs, transform=None, tag="main", with_carbon=False):
    """pairs: list of (item, trip_key). Returns rows with Overheard and baseline predictions."""
    trans_cache = {}

    def prep(item):
        data, mime = load(item)
        if transform:
            data, mime = transform(item, data, mime)
        return data, mime

    datas = {it["id"]: prep(it) for it in {p[0]["id"]: p[0] for p in pairs}.values()}
    tfuts = {iid: POOL.submit(transcribe, *datas[iid], f"{iid}/{tag}") for iid in datas}
    ofuts = [(it, k, POOL.submit(overheard, *datas[it["id"]], k, f"{it['id']}/{k}/{tag}")) for it, k in pairs]
    for iid, f in tfuts.items():
        try:
            trans_cache[iid] = f.result()
        except Exception as e:  # noqa: BLE001
            trans_cache[iid] = (f"ERROR {e}", 0)
    rfuts = [(it, k, POOL.submit(text_relevance, trans_cache[it["id"]][0], k, f"{it['id']}/{k}/{tag}")) for it, k in pairs]
    rows = []
    for (it, k, of), (_, _, rf) in zip(ofuts, rfuts):
        o = of.result()
        try:
            rel, rlat = rf.result()
        except Exception:  # noqa: BLE001
            rel, rlat = False, 0
        text, tlat = trans_cache[it["id"]]
        rows.append({"id": it["id"], "modality": it["modality"], "trip": k, "truth": k in it["relevant"],
                     "relevance": o["relevance"], "direct": o["direct"], "fp": o["fp"], "latency": round(o["latency"], 3),
                     "text_baseline": rel, "text_latency": round(tlat + rlat, 3),
                     "keyword": keyword(text, k), "transcript": text[:300]})
    if with_carbon:
        band = [r for r in rows if config.CONFLICT_AT <= r["relevance"] < config.ALERT_AT]
        def cb(r):
            d, m = shrink(*datas[r["id"]])
            try:
                return alert.carbon_band(d, m, TRIPS[r["trip"]], {"relevance": r["relevance"], "top_hits": []})["relevant"]
            except Exception:  # noqa: BLE001
                return False
        for r, v in zip(band, POOL.map(cb, band)):
            r["carbon"] = v
        for r in rows:
            r["policy"] = r["relevance"] >= config.ALERT_AT or bool(r.get("carbon"))
    return rows


def summarize(rows):
    out = {}
    for mod in sorted({r["modality"] for r in rows}):
        rs = [r for r in rows if r["modality"] == mod]
        lat = sorted(r["latency"] for r in rs); tl = sorted(r["text_latency"] for r in rs)
        out[mod] = {"n_pairs": len(rs), "positives": sum(r["truth"] for r in rs),
                    "overheard_alert_0.8": metrics(rs, "relevance", config.ALERT_AT),
                    "overheard_0.5": metrics(rs, "relevance", 0.5),
                    "band_0.4_0.8": sum(config.CONFLICT_AT <= r["relevance"] < config.ALERT_AT for r in rs),
                    "text_baseline": metrics(rs, "text_baseline"), "keyword": metrics(rs, "keyword"),
                    "latency_median_s": lat[len(lat) // 2], "latency_p90_s": lat[int(len(lat) * .9)],
                    "text_baseline_latency_median_s": tl[len(tl) // 2]}
    return out


def main_eval():
    items = [i for i in LABELS if i["modality"] in ("audio", "image")]
    real = [{"id": p.stem, "modality": "image", "file": str(p.relative_to(ROOT)), "relevant": rel, "source": "real"}
            for p, rel in [(ROOT / "data/real/images/7_train_service_change_notice_4_languages.jpg", []),
                           (ROOT / "data/real/images/g_train_service_change_sign.jpg", []),
                           (ROOT / "data/real/images/r_train_service_change_sign_9th_st.jpg", []),
                           (ROOT / "data/real/images/times_square_platform_sign.jpg", [])] if p.exists()]
    # real 7 poster: no 7 between Flushing-Main St and Mets-Willets Point -> affects T3 (alighting station)
    for r in real:
        if r["id"].startswith("7_train"):
            r["relevant"] = ["T3"]
    pairs = [(it, k) for it in items + real for k in TRIPS]
    rows = run_pairs(pairs)
    (OUT / "main_rows.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    summ = summarize(rows)
    (OUT / "main_summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))
    misses = [r for r in rows if (r["relevance"] >= config.ALERT_AT) != r["truth"]]
    print("Overheard misses at 0.8:", [(r["id"], r["trip"], r["truth"], r["relevance"]) for r in misses])


# ---------- breaking points ----------
def _noise_bed(n_samples: int, sr=16000) -> np.ndarray:
    clips = sorted((ROOT / "data" / "real" / "audio").glob("*.wav"))
    bed = []
    for c in clips:
        out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(c), "-ac", "1", "-ar", str(sr), "-f", "s16le", "pipe:1"],
                             capture_output=True, check=True).stdout
        bed.append(np.frombuffer(out, np.int16).astype(np.float32))
    bed = np.concatenate(bed) if bed else np.random.randn(n_samples).astype(np.float32) * 3000
    bed = np.tile(bed, n_samples // len(bed) + 1)[:n_samples]
    return bed


def add_noise(snr_db):
    def f(item, data, mime):
        sr = 16000
        pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(sr), "-f", "s16le", "pipe:1"],
                             input=data, capture_output=True, check=True).stdout
        x = np.frombuffer(pcm, np.int16).astype(np.float32)
        n = _noise_bed(len(x))
        ps, pn = np.mean(x ** 2) + 1e-9, np.mean(n ** 2) + 1e-9
        y = x + n * np.sqrt(ps / (pn * 10 ** (snr_db / 10)))
        y = np.clip(y, -32768, 32767).astype(np.int16).tobytes()
        wav = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0",
                              "-f", "wav", "pipe:1"], input=y, capture_output=True, check=True).stdout
        return wav, "audio/wav"
    return f


def degrade_image(level):
    def f(item, data, mime):
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((1024, 1024))
        if level:
            im = im.filter(ImageFilter.GaussianBlur(level))
            # glare: brighten a soft radial patch
            w, h = im.size
            yy, xx = np.mgrid[0:h, 0:w]
            mask = np.exp(-(((xx - w * .6) ** 2 + (yy - h * .4) ** 2) / (2 * (w * .25) ** 2)))
            a = np.asarray(im).astype(np.float32)
            a = a + (255 - a) * mask[..., None] * min(0.9, level / 12)
            im = Image.fromarray(a.clip(0, 255).astype(np.uint8))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    return f


def breaking(modality, levels, make, name, xlabel):
    random.seed(0)
    items = [i for i in LABELS if i["modality"] == modality]
    pos = [(i, k) for i in items for k in i["relevant"]]
    negs = [(i, k) for i in items for k in TRIPS if k not in i["relevant"]]
    pairs = pos + random.sample(negs, len(pos))
    res = []
    for lv in levels:
        rows = run_pairs(pairs, make(lv), tag=f"{name}{lv}", with_carbon=True)
        (OUT / f"{name}_rows_{lv}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
        m = {"level": lv, "policy": metrics(rows, "policy"), "overheard": metrics(rows, "relevance", config.ALERT_AT),
             "text_baseline": metrics(rows, "text_baseline"), "keyword": metrics(rows, "keyword")}
        res.append(m)
        print(name, lv, {k: (v["precision"], v["recall"], v["fp"]) for k, v in m.items() if k != "level"}, flush=True)
    (OUT / f"{name}.json").write_text(json.dumps(res, indent=1))
    chart(res, name, xlabel)


def chart(res, name, xlabel):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    xs = [str(r["level"]) for r in res]
    for key, lbl, c in [("policy", "Overheard full policy (Decision 1 + Carbon band)", "#e4572e"),
                        ("overheard", "Decision 1 alone, alert at 0.8", "#f3a712"),
                        ("text_baseline", "Transcribe then ask Hydrogen", "#29335c"),
                        ("keyword", "Keyword match", "#8a909c")]:
        axes[0].plot(xs, [r[key]["recall"] for r in res], "o-", label=lbl, color=c)
        axes[1].plot(xs, [r[key]["fp"] for r in res], "o-", label=lbl, color=c)
    axes[0].set_title("Recall (relevant changes caught)"); axes[0].set_ylim(-0.05, 1.05)
    axes[1].set_title("False interruptions (count)")
    for a in axes: a.set_xlabel(xlabel); a.grid(alpha=.3)
    axes[0].legend(fontsize=7, loc="lower left")
    fig.suptitle(f"Breaking point: {name}"); fig.tight_layout()
    fig.savefig(CH / f"{name}.png", dpi=130); plt.close(fig)


# ---------- video ----------
def video_eval():
    rows = []
    for it in [i for i in LABELS if i["modality"] == "video"]:
        frames = sample_frames(ROOT / it["file"])
        for k in TRIPS:
            futs = [(t, POOL.submit(score_bytes, f, "image/jpeg", TRIPS[k], FPS[k], f"{it['id']}@{t}/{k}")) for t, f in frames]
            tl = [{"t": round(t, 1), "relevance": fu.result()["relevance"], "latency": fu.result()["latency_s"]} for t, fu in futs]
            segs = segments(tl, config.ALERT_AT, pad=0)
            truth_m = [m for m in it.get("moments", []) if k in m["relevant"]]
            hit = bool(segs)
            located = any(s < m["end"] and e > m["start"] for s, e in segs for m in truth_m)
            rows.append({"id": it["id"], "trip": k, "truth": bool(truth_m), "alerted": hit, "located": located,
                         "segments": segs, "max_rel": max(p["relevance"] for p in tl),
                         "frame_latency_median": sorted(p["latency"] for p in tl)[len(tl) // 2]})
            print(rows[-1], flush=True)
    m = metrics(rows, "alerted")
    m["moment_located"] = sum(r["located"] for r in rows if r["truth"])
    (OUT / "video.json").write_text(json.dumps({"rows": rows, "metrics": m}, indent=1))
    print(m)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("main", "all"): main_eval()
    if what in ("noise", "all"): breaking("audio", [None, 10, 5, 0, -5, -10], lambda lv: None if lv is None else add_noise(lv), "audio_noise", "SNR dB (None = clean; venue/train noise from real Commons recordings)")
    if what in ("blur", "all"): breaking("image", [0, 2, 4, 8, 12], degrade_image, "image_blur_glare", "Gaussian blur radius px + glare")
    if what in ("video", "all"): video_eval()
