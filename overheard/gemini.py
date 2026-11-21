"""Shared Gemini client plus a logging wrapper: every call records model, prompt summary and latency."""
import json, os, time, threading
from pathlib import Path
from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
LOG = ROOT / "logs" / "calls.jsonl"
LOG.parent.mkdir(exist_ok=True)


_CLIENT = None
_LOCK = threading.Lock()


def client() -> genai.Client:
    """One shared client for every thread (two racing clients close each other's connection pool)."""
    global _CLIENT
    with _LOCK:
        if _CLIENT is None:
            _CLIENT = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"api_version": "v1beta"})
        return _CLIENT


def log_call(model: str, summary: str, latency_s: float, **extra):
    rec = {"t": time.strftime("%H:%M:%S"), "model": model, "summary": summary[:120],
           "latency_s": round(latency_s, 3), **extra}
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[gemini] {model} {latency_s:.2f}s  {summary[:80]}", flush=True)


def timed(_model: str, _summary: str, fn, *args, retries: int = 3, **kwargs):
    """Run fn(*args, **kwargs), retry 503/500 with backoff, log model and latency."""
    for attempt in range(retries):
        t0 = time.time()
        try:
            out = fn(*args, **kwargs)
            log_call(_model, _summary, time.time() - t0)
            return out
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if attempt < retries - 1 and any(c in msg for c in ("503", "500", "UNAVAILABLE", "overloaded")):
                time.sleep(1.5 * (attempt + 1))
                continue
            log_call(_model, _summary + f" ERROR {msg[:80]}", time.time() - t0, error=True)
            raise
