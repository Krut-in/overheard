"""Build 4 synthetic 15 s station walkthrough videos from the poster images (3 s per sign, slow pan), with labels."""
import json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SEQS = {  # video id: posters in order (3 s each)
    "v1": ["i13", "i04", "i01", "i16", "i05"],   # Q weekend poster at 6-9 s -> T1
    "v2": ["i16", "i08", "i02", "i14", "i18"],   # F reroute poster at 6-9 s -> T2
    "v3": ["i06", "i11", "i15", "i09", "i13"],   # 7 express suspended clock at 9-12 s -> T3
    "v4": ["i05", "i13", "i14", "i16", "i18"],   # nothing relevant
}
labels = json.loads((ROOT / "labels.json").read_text())
rel = {i["id"]: i["relevant"] for i in labels["items"]}
labels["items"] = [i for i in labels["items"] if i["modality"] != "video"]
for vid, seq in SEQS.items():
    out = ROOT / "synth" / "video" / f"{vid}.mp4"
    args, filt = [], []
    for n, iid in enumerate(seq):
        args += ["-i", str(ROOT / "synth" / "images" / f"{iid}.png")]
        filt.append(f"[{n}:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,zoompan=z='min(zoom+0.0015,1.12)':d=75:s=1280x720:fps=25,setsar=1[v{n}]")
    filt.append("".join(f"[v{n}]" for n in range(len(seq))) + f"concat=n={len(seq)}:v=1:a=0[out]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args, "-filter_complex", ";".join(filt), "-map", "[out]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "15", str(out)], check=True)
    trips = sorted({t for iid in seq for t in rel[iid]})
    moments = [{"start": 3 * n, "end": 3 * n + 3, "id": iid, "relevant": rel[iid]} for n, iid in enumerate(seq) if rel[iid]]
    labels["items"].append({"id": vid, "modality": "video", "file": f"data/synth/video/{vid}.mp4", "relevant": trips,
                            "moments": moments, "text": " | ".join(seq), "source": "synthetic"})
    print(vid, trips, moments)
(ROOT / "labels.json").write_text(json.dumps(labels, indent=1, ensure_ascii=False))
