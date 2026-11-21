"""Takes a true 375 px phone screenshot of a URL with headless Chrome over the DevTools protocol.

Plain `chrome --headless --window-size=375,...` clamps the layout viewport to 500 px, so the page would not be
laid out at phone width. This emulates a 375 px mobile viewport instead.
Run: .venv/bin/python web/abroad/shot.py <url> docs/abroad_375.png [height]
"""
import base64, json, subprocess, sys, tempfile, time
import httpx
from websockets.sync.client import connect

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def shot(url: str, out: str, width: int = 375, height: int = 1600, port: int = 9333):
    prof = tempfile.mkdtemp(prefix="ovh_chrome_")
    proc = subprocess.Popen([CHROME, "--headless", f"--remote-debugging-port={port}", f"--user-data-dir={prof}",
                             "--hide-scrollbars", "--no-first-run", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = httpx.get(f"http://127.0.0.1:{port}/json").json()
                page = next(t for t in tabs if t["type"] == "page")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        with connect(page["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
            n = 0

            def call(method, **params):
                nonlocal n
                n += 1
                ws.send(json.dumps({"id": n, "method": method, "params": params}))
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get("id") == n:
                        return msg.get("result", {})
            call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=2, mobile=True)
            call("Emulation.setUserAgentOverride", userAgent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                 "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
            call("Page.enable")
            call("Page.navigate", url=url)
            time.sleep(5)  # fonts, first /feed polls, entry animations
            w = call("Runtime.evaluate", expression="innerWidth+'x'+innerHeight+' scrollW='+document.documentElement.scrollWidth")
            print("viewport", w["result"]["value"])
            img = call("Page.captureScreenshot", format="png")
        with open(out, "wb") as f:
            f.write(base64.b64decode(img["data"]))
        print("wrote", out)
    finally:
        proc.terminate()


if __name__ == "__main__":
    shot(sys.argv[1], sys.argv[2], height=int(sys.argv[3]) if len(sys.argv) > 3 else 1600)
