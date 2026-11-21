"""Station walkthrough video: sample one frame per second, score each with the same Decision 1 fingerprint,
find the relevant moments, cut a captioned highlight clip with ffmpeg, and alert on the best frame."""
import subprocess, tempfile
from pathlib import Path
from overheard import config
from overheard.decide import score_bytes
from overheard.gemini import ROOT

OUT = ROOT / "logs" / "videos"
OUT.mkdir(parents=True, exist_ok=True)
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def sample_frames(path: Path, fps: float = 1.0) -> list[tuple[float, bytes]]:
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf", f"fps={fps},scale=768:-2",
                    "-q:v", "4", str(tmp / "f_%03d.jpg")], check=True)
    frames = sorted(tmp.glob("f_*.jpg"))
    return [((i + 0.5) / fps, f.read_bytes()) for i, f in enumerate(frames)]


def segments(timeline: list[dict], threshold: float, pad: float = 1.0) -> list[tuple[float, float]]:
    hits = [p["t"] for p in timeline if p["relevance"] >= threshold]
    segs = []
    for t in hits:
        s, e = max(0, t - 0.5 - pad), t + 0.5 + pad
        if segs and s <= segs[-1][1]:
            segs[-1] = (segs[-1][0], e)
        else:
            segs.append((s, e))
    return segs


def _esc(text: str) -> str:
    return text.replace("\\", "").replace(":", " -").replace("'", "").replace("%", " pct")[:72]


def cut_highlight(src: Path, segs: list[tuple[float, float]], caption: str, dst: Path) -> Path:
    """Local ffmpeg: keep only the relevant seconds, burn in the change as a caption."""
    sel = "+".join(f"between(t,{s:.2f},{e:.2f})" for s, e in segs)
    vf = f"select='{sel}',setpts=N/FRAME_RATE/TB"
    if Path(FONT).exists():
        vf += (f",drawtext=fontfile={FONT}:text='{_esc(caption)}':x=(w-tw)/2:y=h-th-40:fontsize=26:"
               "fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=12")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", vf, "-an",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)], check=True)
    return dst


def process_video(ev, raw: bytes, name: str, state: dict, pool, hit_cb):
    try:
        src = OUT / f"{ev['id']}{Path(name).suffix or '.mp4'}"
        src.write_bytes(raw)
        frames = sample_frames(src)
        ev["status"] = f"scoring {len(frames)} frames"
        futs = [(t, f, pool.submit(score_bytes, f, "image/jpeg", state["trip"], state["fp"], f"{name}@{t:.1f}s"))
                for t, f in frames]
        timeline, best = [], None
        for t, f, fu in futs:
            s = fu.result()
            timeline.append({"t": round(t, 1), "relevance": s["relevance"], "type": s["change_type"]})
            if best is None or s["relevance"] > best[0]:
                best = (s["relevance"], t, f, s)
        ev["timeline"] = timeline
        ev["scores"] = best[3]
        segs = segments(timeline, config.ALERT_AT)
        ev["segments"] = segs
        if not segs:
            ev["status"] = "silent"
            ev["route"] = "silence"
            ev["caption"] = f"walkthrough, no relevant sign (max {best[0]:.2f} at {best[1]:.0f}s)"
            return
        ev["route"] = "alert"
        ev["best_t"] = best[1]
        hit_cb(ev, best[2])
        dst = OUT / f"{ev['id']}_highlight.mp4"
        cut_highlight(src, segs, ev.get("change", {}).get("change", "relevant sign"), dst)
        ev["clip"] = f"/clips/videos/{dst.name}"
        ev["clip_by"] = "local ffmpeg"
        if config.USE_MANAGED_AGENT:
            pool.submit(_agent_clip, ev, raw, segs, ev.get("change", {}).get("change", "relevant sign"))
        ev["caption"] = f"{len(segs)} relevant moment(s) in {timeline[-1]['t']:.0f}s of video"
    except Exception as e:  # noqa: BLE001
        ev["status"] = "error"
        ev["error"] = str(e)[:300]


def _agent_clip(ev, raw: bytes, segs, caption: str):
    try:
        from overheard.agent_clip import agent_highlight
        ev["agent_status"] = "Managed Agent cutting the clip in a hosted sandbox…"
        clip, meta = agent_highlight(raw, segs, caption)
        dst = OUT / f"{ev['id']}_agent.mp4"
        dst.write_bytes(clip)
        ev["clip"] = f"/clips/videos/{dst.name}"
        ev["clip_by"] = f"Gemini Managed Agent ({config.MANAGED_AGENT}), ffmpeg in a hosted sandbox, {meta['seconds']} s"
        ev["agent_status"] = "done"
    except Exception as e:  # noqa: BLE001
        ev["agent_status"] = f"agent failed, kept local clip: {str(e)[:120]}"
