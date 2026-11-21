"""Live-capture demo video for Overheard abroad (375x812 phone viewport -> docs/overheard_demo_live.mp4).

Drives http://localhost:8001/abroad with headless Chromium via Playwright (`record_video_dir`),
follows the "Trip abroad on a phone" sequence in DEMO.md, maps the recorded chapters to the
exact 60 s timeline, burns in the DEMO.md voiceover lines as ASS subtitles, and writes
docs/overheard_demo_live.mp4.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = "http://localhost:8001/abroad"
BOARD_PHOTO = ROOT / "data" / "abroad" / "rehearsal" / "train_ams_3.jpg"
OUT_MP4 = ROOT / "docs" / "overheard_demo_live.mp4"

VIEWPORT = {"width": 375, "height": 812}
OUT_W, OUT_H = 750, 1624
FPS = 30

# Verbatim DEMO.md voiceover lines split into readable cues within each exact DEMO.md window.
SUBTITLES = [
    # 0:00 to 0:08
    (0.2, 3.2, r"This is my trip to Paris and Amsterdam: six bookings."),
    (3.2, 7.9, r"Hydrogen turns them into one fingerprint of about 290 questions,\Neach tagged with the booking it protects."),
    # 0:08 to 0:20
    (8.1, 12.0, r"Before I fly, it reads French and Dutch news for my dates."),
    (12.0, 15.8, r"Almost all of it stays silent, with a receipt."),
    (15.8, 19.9, r"The tram works by my Amsterdam hotel do not."),
    # 0:20 to 0:35
    (20.1, 25.5, r"On the platform, every announcement goes through\None Decision call in about a second."),
    (25.5, 29.5, r"The 9317 is not my train."),
    (29.5, 34.9, r"The 9315 is, and it tells me in Hindi."),
    # 0:35 to 0:45
    (35.1, 44.9, r"Point the camera at the board and I get my own photo back,\Nwith my train circled."),
    # 0:45 to 0:55
    (45.1, 48.6, r"When it gets one wrong, I say not about me."),
    (48.6, 54.9, r"It writes sharper questions for that booking, checks they stay quiet\Non real alerts, and the same mistake goes silent."),
    # 0:55 to 1:00
    (55.1, 59.9, r"All eighteen rehearsal changes caught, under a second each for most,\Nand every failure is in the README."),
]

RESULTS_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Figtree:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root { --paper:#f1ece2; --card:#fbf8f2; --ink:#1c1b19; --ink-2:#4a4740; --mute:#8d877b;
    --hair:#d8d1c2; --signal:#d63c1e; --calm:#5e7a6a; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink); font:13.5px/1.4 Figtree, sans-serif;
    padding:20px 16px 24px; min-height:100vh; }
  .mark { font:italic 28px/1 "Instrument Serif", Georgia, serif; margin-bottom:4px; }
  .mark i { font-style:normal; color:var(--signal); }
  .sub { font:11px "DM Mono", monospace; color:var(--mute); text-transform:uppercase; letter-spacing:1.3px;
    padding-bottom:12px; border-bottom:1px solid var(--hair); margin-bottom:14px; }
  .kpi { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:14px; }
  .box { background:var(--card); border:1px solid var(--hair); border-radius:12px; padding:10px 12px; }
  .box b { display:block; font:30px/1 "Instrument Serif", Georgia, serif; color:var(--ink); }
  .box b.hot { color:var(--signal); }
  .box span { font:10.5px "DM Mono", monospace; color:var(--mute); }
  table { width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--hair);
    border-radius:12px; overflow:hidden; font-size:11.5px; }
  th { text-align:left; font:500 9.5px "DM Mono", monospace; text-transform:uppercase; letter-spacing:.8px;
    color:var(--mute); padding:8px 8px 6px; border-bottom:1px solid var(--hair); background:#f6f2e9; }
  td { padding:7px 8px; border-bottom:1px solid var(--hair); vertical-align:top; }
  tr:last-child td { border-bottom:none; }
  tr.hi td { font-weight:600; background:#fdf4f0; }
  .mono { font-family:"DM Mono", monospace; font-size:11px; white-space:nowrap; }
  .sec { font:500 10px "DM Mono", monospace; text-transform:uppercase; letter-spacing:1.1px;
    color:var(--ink-2); background:#ede7da; }
  .foot { margin-top:12px; font:11.5px/1.45 Figtree, sans-serif; color:var(--ink-2); }
  .foot code { font:11px "DM Mono", monospace; color:var(--signal); }
</style></head><body>
  <div class="mark">Overheard<i>.</i></div>
  <div class="sub">Abroad eval · 74 items · 6 bookings</div>
  <div class="kpi">
    <div class="box"><b class="hot">18 / 18</b><span>rehearsal changes caught</span></div>
    <div class="box"><b>0.56 – 0.93 s</b><span>median Decision 1 latency</span></div>
  </div>
  <table>
    <thead><tr><th>Method</th><th>Caught</th><th>False</th><th>Med.</th></tr></thead>
    <tbody>
      <tr><td colspan="4" class="sec">Rehearsal audio (12 hits, 12 near misses)</td></tr>
      <tr><td>Decision 1 at 0.8</td><td class="mono">10/12</td><td class="mono">2/12</td><td class="mono">0.93s</td></tr>
      <tr class="hi"><td>Full policy (+Carbon)</td><td class="mono">12/12</td><td class="mono">2/12</td><td class="mono">2.6s</td></tr>
      <tr><td>Keyword match</td><td class="mono">12/12</td><td class="mono">10/12</td><td class="mono">—</td></tr>
      <tr><td colspan="4" class="sec">Rehearsal signs (6 hits, 6 near misses)</td></tr>
      <tr><td>Decision 1 at 0.8</td><td class="mono">5/6</td><td class="mono">0/6</td><td class="mono">0.56s</td></tr>
      <tr class="hi"><td>Full policy (+Carbon)</td><td class="mono">6/6</td><td class="mono">1/6</td><td class="mono">2.3s</td></tr>
      <tr><td colspan="4" class="sec">Real radar news (3 hits, 35 not)</td></tr>
      <tr><td>Decision 1 at 0.8</td><td class="mono">3/3</td><td class="mono">5/35</td><td class="mono">0.73s</td></tr>
      <tr class="hi"><td>Full policy (+Carbon)</td><td class="mono">3/3</td><td class="mono">6/35</td><td class="mono">0.76s</td></tr>
    </tbody>
  </table>
  <div class="foot">Every failure, near-miss and learning curve is documented in <code>README.md</code>.</div>
</body></html>
"""


def _ass_time(sec: float) -> str:
    cs = int(round(sec * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def write_ass(path: Path) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Helvetica Neue,25,&H00F2F8FB,&H000000FF,&H38191B1C,&H38191B1C,0,0,0,0,100,100,0,0,3,10,0,2,32,32,192,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header.rstrip()]
    for start, end, text in SUBTITLES:
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tap_ripple(page: Page, locator) -> None:
    """Show a subtle touch ripple at the center of an element right before clicking."""
    box = locator.bounding_box()
    if box:
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        page.evaluate(
            """([x, y]) => {
                const el = document.createElement('div');
                el.style.cssText = `position:fixed;left:${x-22}px;top:${y-22}px;width:44px;height:44px;` +
                    `border-radius:50%;background:rgba(214,60,30,0.38);border:2px solid rgba(214,60,30,0.9);` +
                    `pointer-events:none;z-index:99999;transform:scale(0.5);transition:transform .4s ease-out,opacity .4s ease-out;`;
                document.body.appendChild(el);
                requestAnimationFrame(() => { el.style.transform = 'scale(1.45)'; el.style.opacity = '0'; });
                setTimeout(() => el.remove(), 450);
            }""",
            [cx, cy],
        )
        time.sleep(0.25)


def smooth_scroll(page: Page, y: int, steps: int = 12, dt: float = 0.04) -> None:
    cur = page.evaluate("window.scrollY")
    for i in range(1, steps + 1):
        val = cur + (y - cur) * (i / steps)
        page.evaluate("v => window.scrollTo(0, v)", val)
        time.sleep(dt)


def center_in_view(page: Page, locator, offset: int = -110) -> None:
    """Scroll smoothly so the locator sits cleanly in the upper-middle of the viewport, above dock & subtitles."""
    box = locator.bounding_box()
    if not box:
        locator.scroll_into_view_if_needed()
        return
    target_y = page.evaluate("window.scrollY") + box["y"] + offset
    smooth_scroll(page, max(0, int(target_y)), steps=12, dt=0.03)


def fetch_feed(page: Page) -> dict:
    return page.evaluate("async () => (await fetch('/api/abroad/feed')).json()")


def force_render(page: Page) -> None:
    page.evaluate(
        """async () => {
            const f = await (await fetch('/api/abroad/feed')).json();
            if (typeof IT !== 'undefined' && f.itinerary_id) {
                IT = await (await fetch('/api/abroad/itinerary')).json();
            }
            FEED = f;
            render(f);
        }"""
    )


def wait_scoring_done(page: Page, min_events: int = 1, timeout: float = 65.0) -> dict:
    deadline = time.monotonic() + timeout
    last_feed = {"events": []}
    while time.monotonic() < deadline:
        last_feed = fetch_feed(page)
        evs = last_feed.get("events", [])
        scoring = sum(1 for e in evs if e.get("status") == "scoring")
        if len(evs) >= min_events and scoring == 0:
            return last_feed
        time.sleep(0.8)
    return last_feed


def record_session(raw_dir: Path) -> tuple[Path, list[tuple[float, float, float]]]:
    """Drive the real phone page and return (raw_video_path, [(src_start, src_end, target_dur), ...])."""
    segments: list[tuple[float, float, float]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
            ),
            record_video_dir=str(raw_dir),
            record_video_size=VIEWPORT,
        )
        page = context.new_page()
        t0 = time.monotonic()
        now = lambda: time.monotonic() - t0  # noqa: E731

        # Start visually on the empty page even if the server already holds a prior session's events;
        # unroute immediately before clicking "trip" so every live interaction hits port 8001.
        empty_route = lambda route: route.fulfill(  # noqa: E731
            status=200,
            content_type="application/json",
            body=json.dumps({"itinerary_id": None, "lang": "Hindi", "fixture": False, "events": []}),
        )
        page.route("**/api/abroad/feed", empty_route)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_selector("button[aria-label='Load demo trip']", timeout=15000)
        time.sleep(0.5)

        # ---- Chapter 1 (0:00 -> 0:08, 8.0 s): Empty page -> tap "trip" -> timeline fills ----
        c1_start = now()
        print(f"[{c1_start:6.2f}s] Ch1: empty page -> tap trip", flush=True)
        time.sleep(2.2)
        page.unroute("**/api/abroad/feed", empty_route)
        trip_btn = page.locator("button[aria-label='Load demo trip']")
        tap_ripple(page, trip_btn)
        trip_btn.click()
        page.wait_for_selector("#tripSec:not([hidden]) #timeline li:nth-child(6)", timeout=45000)
        time.sleep(1.2)
        # Scroll to showcase all 6 bookings in the timeline clearly
        tl_y = page.evaluate("document.getElementById('tripSec').getBoundingClientRect().top + window.scrollY - 60")
        smooth_scroll(page, max(0, int(tl_y)), steps=14, dt=0.04)
        time.sleep(2.4)
        smooth_scroll(page, 0, steps=10, dt=0.03)
        time.sleep(0.5)
        c1_end = now()
        segments.append((c1_start, c1_end, 8.0))
        print(f"[{c1_end:6.2f}s] Ch1 done (raw {c1_end - c1_start:.2f}s -> 8.0s)", flush=True)

        # ---- Chapter 2 (0:08 -> 0:20, 12.0 s): Tap "radar" -> receipts + red Amsterdam alert ----
        c2_start = now()
        print(f"[{c2_start:6.2f}s] Ch2: tap radar", flush=True)
        radar_btn = page.locator("button[aria-label='Radar']")
        tap_ripple(page, radar_btn)
        radar_btn.click()
        time.sleep(2.2)
        c2_wait_start = now()

        # Wait for radar scoring to finish (38 items in pool of 3)
        feed = wait_scoring_done(page, min_events=20, timeout=75.0)
        force_render(page)
        time.sleep(0.6)
        c2_reveal_start = now()

        # Show top radar alert(s), then scroll down past timeline to silence receipts
        alerts_count = sum(1 for e in feed.get("events", []) if e.get("status") == "alert")
        silent_count = sum(1 for e in feed.get("events", []) if e.get("status") == "silent")
        print(f"[{c2_reveal_start:6.2f}s] Radar settled: {alerts_count} alerts, {silent_count} silent", flush=True)
        time.sleep(1.8)
        rc_y = page.evaluate("document.getElementById('rcSec').getBoundingClientRect().top + window.scrollY - 70")
        smooth_scroll(page, max(0, int(rc_y)), steps=16, dt=0.04)
        time.sleep(1.8)
        smooth_scroll(page, 0, steps=12, dt=0.03)
        time.sleep(0.8)
        c2_end = now()
        segments.append((c2_start, c2_wait_start, 2.5))
        segments.append((c2_wait_start, c2_reveal_start, 4.5))
        segments.append((c2_reveal_start, c2_end, 5.0))
        print(f"[{c2_end:6.2f}s] Ch2 done (raw {c2_end - c2_start:.2f}s -> 12.0s)", flush=True)

        # ---- Chapter 3 (0:20 -> 0:35, 15.0 s): Tap "rehearse" -> 9315 alert -> tap Whisper ----
        c3_start = now()
        prev_n = len(fetch_feed(page).get("events", []))
        print(f"[{c3_start:6.2f}s] Ch3: tap rehearse (prev events={prev_n})", flush=True)
        reh_btn = page.locator("button[aria-label='Rehearse']")
        tap_ripple(page, reh_btn)
        reh_btn.click()
        time.sleep(2.2)
        c3_wait_start = now()

        feed = wait_scoring_done(page, min_events=prev_n + 10, timeout=90.0)
        # Also wait briefly for Eurostar 9315 alert whisper_url to land
        deadline = time.monotonic() + 25.0
        while time.monotonic() < deadline:
            feed = fetch_feed(page)
            evs = feed.get("events", [])
            hit_9315 = next(
                (e for e in evs if e.get("status") == "alert" and (e.get("alert") or {}).get("booking_id") == "train_ams"),
                None,
            )
            if hit_9315 and (hit_9315.get("alert") or {}).get("whisper_url"):
                break
            time.sleep(0.8)
        force_render(page)
        time.sleep(0.5)
        c3_reveal_start = now()

        # Find the real Eurostar 9315 cancellation alert (train_ams_1) and tap Whisper
        feed = fetch_feed(page)
        ams_evs = [
            e for e in feed.get("events", [])
            if e.get("status") == "alert" and (e.get("alert") or {}).get("booking_id") == "train_ams"
        ]
        target_9315 = next(
            (e for e in ams_evs if (e.get("input") or {}).get("rehearsal_id") == "train_ams_1"),
            max(ams_evs, key=lambda e: (e.get("verdict") or {}).get("relevance", 0.0), default=None),
        )
        if target_9315:
            card_9315 = page.locator(f"article.alert[data-id='{target_9315['id']}']").first
        else:
            card_9315 = page.locator("article.alert", has_text="9315").first
        if card_9315.count() == 0:
            card_9315 = page.locator("article.alert").first
        center_in_view(page, card_9315, offset=-90)
        time.sleep(1.5)
        whisper_btn = card_9315.locator("button", has_text="Whisper").first
        tap_ripple(page, whisper_btn)
        whisper_btn.click()
        time.sleep(2.8)
        # Briefly scroll down to show the Eurostar 9317 silence receipt if present, then back to top
        rc_9317 = page.locator("#receipts .rc", has_text="9317").first
        if rc_9317.count() > 0:
            center_in_view(page, rc_9317, offset=-140)
            time.sleep(1.6)
        smooth_scroll(page, 0, steps=10, dt=0.03)
        time.sleep(0.5)
        c3_end = now()
        segments.append((c3_start, c3_wait_start, 2.5))
        segments.append((c3_wait_start, c3_reveal_start, 5.5))
        segments.append((c3_reveal_start, c3_end, 7.0))
        print(f"[{c3_end:6.2f}s] Ch3 done (raw {c3_end - c3_start:.2f}s -> 15.0s)", flush=True)

        # ---- Chapter 4 (0:35 -> 0:45, 10.0 s): Upload train_ams_3.jpg via #file -> circled photo ----
        c4_start = now()
        print(f"[{c4_start:6.2f}s] Ch4: upload {BOARD_PHOTO.name}", flush=True)
        photo_btn = page.locator("button[aria-label='Upload']")
        tap_ripple(page, photo_btn)
        page.set_input_files("#file", str(BOARD_PHOTO))
        time.sleep(1.8)
        c4_wait_start = now()

        # Poll /feed until our upload event has alert.proof.kind === "photo" and a url
        deadline = time.monotonic() + 85.0
        photo_ev_id = None
        while time.monotonic() < deadline:
            feed = fetch_feed(page)
            for e in feed.get("events", []):
                inp = e.get("input") or {}
                proof = (e.get("alert") or {}).get("proof") or {}
                if inp.get("origin") == "upload" and inp.get("name") == BOARD_PHOTO.name:
                    photo_ev_id = e["id"]
                    if e.get("status") == "alert" and proof.get("kind") == "photo" and proof.get("url"):
                        break
                    if e.get("status") == "silent":
                        break
            else:
                time.sleep(1.0)
                continue
            break

        force_render(page)
        # Wait for the annotated image inside figure.proof to finish loading
        page.evaluate(
            """() => Promise.all(Array.from(document.querySelectorAll('figure.proof img')).map(img =>
                img.complete ? Promise.resolve() : new Promise(r => { img.onload = img.onerror = r; })
            ))"""
        )
        time.sleep(0.5)
        c4_reveal_start = now()
        print(f"[{c4_reveal_start:6.2f}s] Photo alert ready (ev={photo_ev_id})", flush=True)

        smooth_scroll(page, 0, steps=6, dt=0.03)
        proof_fig = page.locator("article.alert figure.proof").first
        if proof_fig.count() > 0:
            center_in_view(page, proof_fig, offset=-140)
            time.sleep(1.6)
            tap_ripple(page, proof_fig)
            proof_fig.click()  # enlarge so the circled 9315 line fills the frame!
            time.sleep(0.4)
            center_in_view(page, proof_fig, offset=-100)
            time.sleep(2.8)
        else:
            time.sleep(4.5)
        c4_end = now()
        segments.append((c4_start, c4_wait_start, 2.0))
        segments.append((c4_wait_start, c4_reveal_start, 3.0))
        segments.append((c4_reveal_start, c4_end, 5.0))
        print(f"[{c4_end:6.2f}s] Ch4 done (raw {c4_end - c4_start:.2f}s -> 10.0s)", flush=True)

        # ---- Chapter 5 (0:45 -> 0:55, 10.0 s): "Not about me" on the KL 641 card ----
        c5_start = now()
        feed = fetch_feed(page)
        kl_evs = [
            e for e in feed.get("events", [])
            if e.get("status") == "alert" and (e.get("alert") or {}).get("booking_id") == "flight_home"
        ]
        # Prefer the near-miss card (flight_home_4 / mentions 643 or normal/schedule/unchanged)
        target_kl = next(
            (
                e for e in kl_evs
                if (e.get("input") or {}).get("rehearsal_id") == "flight_home_4"
                or any(
                    w in ((e.get("alert") or {}).get("change", "") + " " + (e.get("alert") or {}).get("quote", "")).lower()
                    for w in ("643", "on time", "schedule", "schema", "unchanged", "no change", "normal")
                )
            ),
            kl_evs[0] if kl_evs else None,
        )
        print(f"[{c5_start:6.2f}s] Ch5: Not about me on KL 641 (target={target_kl and target_kl['id']}, candidates={len(kl_evs)})", flush=True)

        if target_kl:
            kl_card = page.locator(f"article.alert[data-id='{target_kl['id']}']").first
        else:
            kl_card = page.locator("article.alert", has_text="KL 641").first
            if kl_card.count() == 0:
                kl_card = page.locator("article.alert").last

        center_in_view(page, kl_card, offset=-120)
        time.sleep(1.8)
        not_btn = kl_card.locator("button", has_text="Not about me").first
        tap_ripple(page, not_btn)
        not_btn.click()
        time.sleep(0.5)
        c5_wait_start = now()

        # Wait for /dismiss to finish (card disappears from alerts & shows in dismissed receipts)
        deadline = time.monotonic() + 55.0
        while time.monotonic() < deadline:
            feed = fetch_feed(page)
            if target_kl:
                cur_ev = next((e for e in feed.get("events", []) if e["id"] == target_kl["id"]), None)
                if cur_ev and cur_ev.get("status") == "dismissed":
                    break
            else:
                if any(e.get("status") == "dismissed" for e in feed.get("events", [])):
                    break
            time.sleep(0.8)
        force_render(page)
        time.sleep(0.4)
        c5_reveal_start = now()
        print(f"[{c5_reveal_start:6.2f}s] KL 641 dismissed and learned", flush=True)

        # Show dismissed receipt and updated timeline question count
        dismissed_el = page.locator("#receipts .rc.dismissed").first
        if dismissed_el.count() > 0:
            center_in_view(page, dismissed_el, offset=-140)
            time.sleep(2.4)
        tl_y = page.evaluate("document.getElementById('tripSec').getBoundingClientRect().top + window.scrollY - 60")
        smooth_scroll(page, max(0, int(tl_y)), steps=10, dt=0.03)
        time.sleep(1.8)
        c5_end = now()
        segments.append((c5_start, c5_wait_start, 2.5))
        segments.append((c5_wait_start, c5_reveal_start, 2.5))
        segments.append((c5_reveal_start, c5_end, 5.0))
        print(f"[{c5_end:6.2f}s] Ch5 done (raw {c5_end - c5_start:.2f}s -> 10.0s)", flush=True)

        # ---- Chapter 6 (0:55 -> 1:00, 5.0 s): README results table ----
        c6_start = now()
        print(f"[{c6_start:6.2f}s] Ch6: README results table", flush=True)
        page.set_content(RESULTS_HTML, wait_until="networkidle")
        time.sleep(5.2)
        c6_end = now()
        segments.append((c6_start, c6_end, 5.0))
        print(f"[{c6_end:6.2f}s] Ch6 done (raw {c6_end - c6_start:.2f}s -> 5.0s)", flush=True)

        video_path = Path(page.video.path())
        page.close()
        context.close()
        browser.close()

    return video_path, segments


def build_final_video(raw_video: Path, segments: list[tuple[float, float, float]], work_dir: Path) -> None:
    ass_path = work_dir / "subs.ass"
    write_ass(ass_path)

    # Probe raw video duration to clamp segment end times safely
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(raw_video)],
        check=True, capture_output=True, text=True,
    )
    raw_dur = float(probe.stdout.strip())
    print(f"Raw recorded webm: {raw_video.name} ({raw_dur:.2f}s), {len(segments)} segments", flush=True)

    filters = []
    labels = []
    for i, (s0, s1, target) in enumerate(segments):
        a = max(0.0, min(s0, raw_dur - 0.15))
        b = max(a + 0.1, min(s1, raw_dur))
        scale = target / (b - a)
        filters.append(
            f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)*{scale:.6f},"
            f"fps={FPS},tpad=stop_mode=clone:stop_duration=0.5,trim=duration={target:.4f},setpts=PTS-STARTPTS[v{i}]"
        )
        labels.append(f"[v{i}]")

    # Escape ASS path for ffmpeg filter syntax
    ass_esc = str(ass_path).replace(":", r"\:")
    filters.append(
        f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0,"
        f"scale={OUT_W}:{OUT_H}:flags=lanczos,ass={ass_esc},"
        f"trim=duration=60.0,setpts=PTS-STARTPTS[out]"
    )
    filter_complex = ";".join(filters)

    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-i", str(raw_video),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-t", "60",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    if not BOARD_PHOTO.is_file():
        sys.exit(f"Missing board photo: {BOARD_PHOTO}")
    with tempfile.TemporaryDirectory(prefix="overheard_rec_") as td:
        work = Path(td)
        raw_video, segments = record_session(work)
        build_final_video(raw_video, segments, work)

    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(OUT_MP4)],
        check=True, capture_output=True, text=True,
    )
    print(f"Output: {OUT_MP4}")
    print(f"Duration: {out.stdout.strip()} s")


if __name__ == "__main__":
    main()
