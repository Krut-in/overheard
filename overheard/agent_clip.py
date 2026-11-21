"""Highlight clip through a Gemini Managed Agent: upload the walkthrough to a hosted sandbox, let the
Antigravity agent cut the relevant seconds with ffmpeg, download the result. Falls back to local ffmpeg."""
import json, time, warnings
import httpx
from overheard import config
from overheard.gemini import client, log_call
import os

warnings.filterwarnings("ignore")
BASE = "https://generativelanguage.googleapis.com/v1beta"


def _env_id() -> str:
    r = httpx.post(f"{BASE}/environments", headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, json={}, timeout=60)
    r.raise_for_status()
    d = r.json()
    return d.get("id") or d["name"].split("/")[-1]


def agent_highlight(src_bytes: bytes, segs: list[tuple[float, float]], caption: str) -> tuple[bytes, dict]:
    t0 = time.time()
    c = client()
    env = _env_id()
    key = {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}
    for attempt in range(6):
        r = httpx.put(f"https://generativelanguage.googleapis.com/upload/v1beta/environments/{env}/files/walk.mp4",
                      headers={**key, "Content-Type": "video/mp4"}, content=src_bytes, timeout=120)
        if r.status_code < 300:
            break
        print("upload", r.status_code, r.text[:200]); time.sleep(4)
    r.raise_for_status()
    keep = ", ".join(f"{s:.1f}s to {e:.1f}s" for s, e in segs)
    goal = (f"In the workspace there is walk.mp4. Use ffmpeg (install it with apt-get or pip imageio-ffmpeg if missing) "
            f"to make highlight.mp4 that keeps only these time ranges: {keep}, concatenated, H.264, yuv420p, no audio, "
            f"with this caption burned in at the bottom in white on a dark box: \"{caption[:80]}\". "
            "Save highlight.mp4 in the workspace root, check it plays with ffprobe, then reply DONE with its duration.")
    it = c.interactions.create(agent=config.MANAGED_AGENT, input=goal, environment=env)
    status = getattr(it, "status", None)
    while status in ("in_progress", "queued", "running", None):
        time.sleep(3)
        it = c.interactions.get(id=it.id)
        status = getattr(it, "status", None)
    out = c.environments.files.download(path="highlight.mp4", environment_id=env)
    dt = time.time() - t0
    log_call(config.MANAGED_AGENT, f"agent ffmpeg highlight {keep}", dt)
    return out, {"environment": env, "interaction": it.id, "status": status, "seconds": round(dt, 1)}


if __name__ == "__main__":
    import sys
    b = open(sys.argv[1], "rb").read()
    clip, meta = agent_highlight(b, [(5.0, 10.0)], "Q trains are not running between 57 St and 96 St this weekend")
    open("logs/agent_highlight.mp4", "wb").write(clip)
    print(meta, len(clip))
