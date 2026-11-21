# Solo scope: Overheard, expanded (2026-11-21, 2:15 PM)

**Pitch:** everything you hear or see on a trip, filtered down to the part that's about you. Snap your ticket or say your route. Overheard listens to announcements, reads posters and departure boards, and scans a quick video of the station. It stays silent about everything that doesn't affect you, and when something does, it whispers the change in your language and shows you your own photo with that one line circled and translated.

**Problem statement:** Element 119 (messy real-world audio, images and video, pushed until it breaks).

**What's new:** translators (Apple Live Translation, Pixel Buds, Spoke, Soniox) and Google Lens translate everything. None of them know your trip, none combine what you hear with what you see, and none show why they stayed silent.

## The core trick: one trip fingerprint for every modality
1. **Neon** reads the ticket photo or spoken route and extracts the trip: lines, stops, platform, gate, flight, times.
2. **Hydrogen** expands the trip into 200 to 500 yes/no questions ("mentions Q train?", "mentions 49 St?", "mentions gate B12?", "mentions a delay or skip?"), plus a `choice` for the type of change.
3. **Decision 1** runs the same fingerprint on any input: an announcement audio clip, a poster photo, a departure board photo, or frames from a station video. One call per input, about 0.3 s to 2 s.
4. Every ignored input leaves a **silence receipt**: "ignored, relevance 0.04, poster about the F train."
5. **Above 0.8:** Neon extracts the exact change, Hydrogen translates it, TTS whispers it, and Nano Banana annotates the user's photo. **0.4 to 0.8:** Carbon settles the conflict. **Below 0.4:** silence.

Because Decision 1 accepts audio, images and video in the same request shape, adding a modality means sending a different input block to the same engine. That's what makes this expansion fit in the time left.

## Inputs and outputs
| Media | In or out | Model | Job |
|---|---|---|---|
| Ticket or boarding pass photo | In | Neon | Builds the trip |
| Announcement audio | In | Decision 1, then Neon | Relevance on raw audio, then the exact change in any language |
| Poster and board photos | In | Decision 1, then Neon | Finds the one line that affects you, such as a weekend service-change poster or a departure board |
| Station walkthrough video (15 s) | In | Neon (time-sliced), Decision 1 on sampled frames | Finds every relevant sign in the clip, with timestamps |
| Voice | In and out | TTS (Live API if time allows) | Whispers the alert; spoken follow-up questions |
| Annotated photo | Out | Nano Banana 2.1 | Your own photo with the relevant line circled and translated in place |
| Highlight clip | Out | Managed agent (ffmpeg) | Cuts the walkthrough down to the relevant moments, with captions |
| Conflicts | Reasoning | Carbon | "The board says platform 7, the announcement says 9" |

## Demo (3 minutes)
1. A judge says their route out loud, or snaps their own boarding pass.
2. A speaker plays real announcements in mixed languages over the venue's noise. Silence receipts scroll by, and one alert gets whispered.
3. Hold up a printed weekend service-change poster. The phone shows it back with the one line that matters circled and translated.
4. Play a 15-second station walkthrough video. Overheard returns a 5-second highlight clip of the one relevant sign.
5. Show a conflict: the board and the announcement disagree, and Carbon explains which to trust.

## Proof
- **Audio:** 40 real announcement clips (Wikimedia Commons open-licensed recordings, plus attendees recorded today in their own languages).
- **Images:** 30 photos of real posters and departure boards (Wikimedia Commons, Flickr Creative Commons).
- **Video:** 8 station walkthrough clips from open-licensed sources.
- Every item is labeled relevant or not for 3 test trips.
- **Baselines:** transcribe or OCR, translate, then ask Hydrogen "is this relevant?" in text; and keyword matching.
- **Metrics:** alert precision and recall per modality, false interruptions, accuracy of the extracted change, latency.
- **Breaking-point charts:** add venue noise to the audio and blur or glare to the images until each method fails.
- **Honest failures:** overlapping announcements, heavy accents, station names that sound alike, tiny print, glare.

## Timeline
| Time | Work |
|---|---|
| 2:15 to 2:35 | Collect clips and photos, ticket to trip with Neon |
| 2:35 to 3:20 | Fingerprint engine for audio and image inputs, silence receipts |
| 3:20 to 3:45 | Alert path: Neon extract, translate, TTS whisper, Nano Banana annotated photo |
| 3:45 to 4:05 | Video walkthrough (sampled frames through the same engine) and ffmpeg highlight clip in a managed agent |
| 4:05 to 4:25 | Eval for audio and images, noise and blur breaking-point charts |
| 4:25 to 4:55 | README, 1-minute video, public repo, submit |

## Cut in this order if behind
1. Live API spoken follow-ups.
2. MTA feed check.
3. The video walkthrough, keeping only audio and photos.
4. Carbon conflict demo, falling back to the higher-confidence source.

Never cut: the fingerprint engine, silence receipts, the audio and image evals.
