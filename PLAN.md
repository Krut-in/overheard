# Overheard build plan (2026-11-21)

Milestones follow the `SCOPE.md` timeline. Each one ends with a commit and a `PROGRESS.md` update. If a milestone runs more than 10 minutes late, apply the next item on the `SCOPE.md` cut list.

| Done by | Milestone | Done when |
|---|---|---|
| 2:30 | M0: decisions written, prototype data | 3 announcement clips and 3 poster images exist in `data/` |
| 2:45 | M1: Decision 1 prototype | Latency and accuracy numbers for 3 clips and 3 posters are in `PROGRESS.md`. Stop and report if a call takes over 5 s or misses more than 1 of 6. |
| 3:20 | M2: fingerprint engine | Ticket photo or typed route goes to Neon, which returns a trip. Hydrogen turns it into 200 or more questions. Decision 1 scores audio and images. Every ignored input gets a silence receipt. |
| 3:45 | M3: alert path | Above 0.8: Neon extracts the change, Hydrogen translates it, TTS speaks it, and Nano Banana circles the line on the user's photo. Carbon handles the 0.4 to 0.8 band. Web page shows all of it. |
| 4:05 | M4: video | Sampled frames from a 15 s walkthrough go through the same engine with timestamps. ffmpeg cuts a highlight clip, through the managed agent if it works within 15 min, locally otherwise. |
| 4:20 | M5: eval | Per-modality precision, recall, false interruptions and latency against a keyword baseline, plus noise and blur breaking-point charts. Feature freeze. |
| 4:55 | M6: ship | README with numbers and honest failures, 1-minute demo video script, repo checked for secrets and ready to go public. Submit before 5:00. |

## Layout
- `overheard/config.py`: model IDs and thresholds, the only place they live.
- `overheard/gemini.py`: client plus a logged call wrapper (model, prompt summary, latency) that appends to `logs/calls.jsonl`.
- `overheard/trip.py`, `fingerprint.py`, `decide.py`, `alert.py`, `video.py`: one file per feature.
- `server.py` and `web/index.html`: the demo page.
- `data/`: synthetic and real inputs plus `labels.json`.
- `eval/`: harness, results and charts.
