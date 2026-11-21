# Brief for Gemini CLI: live-capture demo video (optional upgrade)

A 60 s slideshow video is already submitted (`docs/overheard_demo.mp4`, https://youtu.be/aYt0TgLVfYc). Do not overwrite it. Your job is an upgrade: a screen capture of the real phone page.

## Do
1. A fresh server already runs on port 8001 (port 8000 holds an old process; leave it alone). Check: `curl -s -o /dev/null -w "%{http_code}" localhost:8001/abroad` should print 200. Install Playwright into the venv if missing: `uv pip install --python .venv/bin/python playwright && .venv/bin/python -m playwright install chromium`.
2. Drive `http://localhost:8001/abroad` at 375 x 812 with headless Chromium (Playwright for Python, `record_video_dir`). Follow the "Trip abroad on a phone" table in `DEMO.md`: tap "trip", wait for the timeline, "radar", "rehearse", tap "Whisper" on the 9315 alert, then upload `data/abroad/rehearsal/train_ams_3.jpg` through the hidden `#file` input, then "Not about me" on the KL 641 card.
3. Use thinking level low for anything interactive.
4. With ffmpeg, trim to exactly 60 s, burn in the `DEMO.md` voiceover lines as subtitles at their times, and save to `docs/overheard_demo_live.mp4`.
5. Print the output duration with ffprobe.

## Do not
- Touch `secrets/`, `.env`, or any code outside a new `scripts/record_demo.py`.
- Commit or push. The Claude Code session reviews and pushes after a secret scan.
