# Overheard: demo scripts

## Trip abroad on a phone (main demo, about 1 minute)

Start `.venv/bin/uvicorn server:app --port 8000` and `cloudflared tunnel --url http://localhost:8000`, open `<tunnel url>/abroad` on a phone, set the language to Hindi, and screen-record the phone with sound on.

| Time | On screen | Voiceover |
|---|---|---|
| 0:00 to 0:08 | The empty page, then tap "trip". The timeline fills: AF 23, two hotels, the Louvre, Eurostar 9315, KL 641. | "This is my trip to Paris and Amsterdam: six bookings. Hydrogen turns them into one fingerprint of about 290 questions, each tagged with the booking it protects." |
| 0:08 to 0:20 | Tap "radar". Receipts scroll in; a few cards turn red, such as GVB trams skipping Westermarkt by the Amsterdam hotel. | "Before I fly, it reads French and Dutch news for my dates. Almost all of it stays silent, with a receipt. The tram works by my Amsterdam hotel do not." |
| 0:20 to 0:35 | Tap "rehearse". French and Dutch announcements play; "Eurostar 9317 cancelled" stays silent, then "Eurostar 9315 supprime" alerts and the Hindi whisper plays. | "On the platform, every announcement goes through one Decision call in about a second. The 9317 is not my train. The 9315 is, and it tells me in Hindi." |
| 0:35 to 0:45 | Tap "photo" and shoot the printed Gare du Nord board. The alert shows the photo with the 9315 line circled. | "Point the camera at the board and I get my own photo back, with my train circled." |
| 0:45 to 0:55 | On the KL 641 card that says nothing changed, tap "Not about me". Then replay that clip: it lands under 0.4. | "When it gets one wrong, I say not about me. It writes sharper questions for that booking, checks they stay quiet on real alerts, and the same mistake goes silent." |
| 0:55 to 1:00 | Cut to the results table in the README. | "All eighteen rehearsal changes caught, under a second each for most, and every failure is in the README." |

### Before recording
1. Load the demo trip once beforehand so the cached fingerprint loads in under a second.
2. Whispers autoplay only after the first tap on the page, so tap "trip" on camera.
3. The circled photo takes 25 to 35 s; the alert text and whisper come first, so keep talking.

## Subway demo (the fallback)

Record the laptop screen at http://localhost:8000 with system audio on, so the whispers are audible. Set the language to Hindi before you start. Each line below is one shot, with its time on the clock.

| Time | On screen | Voiceover |
|---|---|---|
| 0:00 to 0:06 | Title card: "Overheard". Then a busy station photo. | "A station talks at you all day. Almost none of it is about your trip." |
| 0:06 to 0:14 | Type "Q train from Times Sq-42 St to 72 St" and press Set trip. The trip card shows 197 fingerprint questions, then open "sample questions". | "Tell Overheard your trip. Neon reads it, and Hydrogen turns it into about 200 yes or no questions. That's the trip fingerprint." |
| 0:14 to 0:26 | Click Doors closing, L maintenance and F delays. Three silence receipts appear with their scores. | "Every announcement and sign goes through gemini-decision-1 against that fingerprint in under a second. Whatever isn't about you leaves a silence receipt with its score." |
| 0:26 to 0:38 | Click "Q no circula (ES)". The alert card appears and the Hindi whisper plays. | "This one is in Spanish, and it is about my train. Neon pulls out the change, Hydrogen translates it, and it gets whispered in Hindi." |
| 0:38 to 0:46 | Click "Q weekend poster". The annotated photo appears with the line circled and a Hindi note. | "Snap a poster and you get your own photo back, with the one line that matters circled and translated by Nano Banana." |
| 0:46 to 0:53 | Click "Walkthrough v1". Show the relevance bars and the highlight clip. | "Film a walk through the station. Every frame is scored, and a Gemini Managed Agent cuts the clip down to the one sign that matters with ffmpeg." |
| 0:53 to 1:00 | Click "Poster: Q on track 4", then "Q platform change", then Ask Carbon. Then cut to the eval chart. | "When a poster and an announcement disagree, Carbon picks the live source. On our eval: 20 of 20 changes caught, zero false alerts, 0.8 seconds per input." |

## Before recording
1. Start the server: `.venv/bin/uvicorn server:app --port 8000`.
2. Click Set trip once beforehand, so the cached fingerprint loads in about 7 s instead of about 35 s.
3. Reload the page to clear the feed. The trip stays set.
4. The whisper autoplays only after the first click on the page, so click Set trip on camera.

## If something fails on camera
- Nano Banana is the slowest step (about 10 s). The alert text and the whisper appear first, so keep talking over that gap.
- The Managed Agent clip takes about 60 s. The local ffmpeg clip shows right away and gets replaced later, so the demo never waits for it.
