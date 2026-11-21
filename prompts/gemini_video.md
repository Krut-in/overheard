# Brief for Gemini CLI: live-capture demo video (optional upgrade)

A 60 s slideshow video is already submitted (`docs/overheard_demo.mp4`, https://youtu.be/aYt0TgLVfYc). Do not overwrite it. Your job is an upgrade: a screen capture of the real phone page.

## Do
1. Check the server answers: `curl -s localhost:8000/abroad | head -5`. If not, start it in the background: `.venv/bin/uvicorn server:app --port 8000`.
2. Drive `http://localhost:8000/abroad` at 375 x 812 with headless Chromium (Playwright for Python, `record_video_dir`). Follow the "Trip abroad on a phone" table in `DEMO.md`: tap "trip", wait for the timeline, "radar", "rehearse", tap "Whisper" on the 9315 alert, then upload `data/abroad/rehearsal/train_ams_3.jpg` through the hidden `#file` input, then "Not about me" on the KL 641 card.
3. Use thinking level low for anything interactive.
4. With ffmpeg, trim to exactly 60 s, burn in the `DEMO.md` voiceover lines as subtitles at their times, and save to `docs/overheard_demo_live.mp4`.
5. Print the output duration with ffprobe.

## Do not
- Touch `secrets/`, `.env`, or any code outside a new `scripts/record_demo.py`.
- Commit or push. The Claude Code session reviews and pushes after a secret scan.
