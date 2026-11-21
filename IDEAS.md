# Project ideas, scored against the rubric

Score = 0.35 × Live Demo + 0.25 × Proof It Works + 0.20 × Creativity + 0.20 × Gemini and Decisions use (each out of 10).

Shared pattern: Neon plans and reasons over the video. Hydrogen runs the cheap, high-volume work inside the Antigravity managed agent. Carbon acts as the final verifier where it matters. `gemini-decision-1` gates every step with calibrated confidence and routes low-confidence cases up the chain.

| # | Idea | Live | Proof | Creat. | Gemini | Score | Bonus prizes |
|---|---|---|---|---|---|---|---|
| 1 | Sketch to Shipped App | 9 | 8 | 7 | 9 | 8.35 | Managed Agents |
| 2 | Bug Video to Failing Test | 7 | 9 | 8 | 9 | 8.10 | Managed Agents |
| 3 | Assembly Watchdog | 9 | 7 | 8 | 8 | 8.10 | Shopify (missing part) |
| 4 | Fix-It Cart | 8 | 8 | 7 | 8 | 7.80 | Shopify, Managed Agents |
| 5 | Breadboard Buddy | 8 | 8 | 8 | 7 | 7.80 | Shopify (parts) |
| 6 | Thrift Pile to Storefront | 8 | 7 | 6 | 7 | 7.15 | Shopify |
| 7 | Move-In Walkthrough Report | 7 | 7 | 7 | 7 | 7.00 | none |

## 1. Sketch to Shipped App
- **Pitch:** draw an app on paper or a whiteboard and narrate it, and a managed agent builds, runs and visually checks it until the screenshot matches your drawing.
- **Models:** Neon reads the sketch photo and voice memo, then writes the spec. Antigravity on Hydrogen codes and runs the app in the sandbox and screenshots it with computer use. Decision 1 scores each screenshot against the sketch on a fidelity rubric (`score`, per component). Carbon judges only the final pass.
- **Demo moment:** a judge draws something on a sticky note. Two minutes later it runs, with a side-by-side overlay of sketch and screenshot.
- **Eval:** 30 sketches drawn by other attendees today (never seen). Baseline: one Neon call that writes code from the photo. Metric: component match rate, plus whether the app runs.
- **Risk:** sandbox build time during a 3-minute demo. Mitigate with a pre-warmed sandbox and a small template.

## 2. Bug Video to Failing Test
- **Pitch:** record your screen while a bug happens, and the agent reproduces it in a sandbox browser, writes a failing Playwright test, then proposes the fix.
- **Models:** Neon watches the screen recording (time-sliced video) and extracts the exact steps. Antigravity on Hydrogen replays them in a headless browser with computer use. Decision 1 checks (`noul`) whether the replay frames match the bug frames. Carbon reviews the patch.
- **Demo moment:** a judge breaks a demo app on purpose while recording. The agent shows the red test, then the green one.
- **Eval:** 30 seeded bugs across 3 open-source apps. Baseline: the same agent given only a typed bug report. Metric: reproduced rate and fix-passes-tests rate.
- **Risk:** less visual on stage than ideas 1 or 3. Fits Problem Statement One best.

## 3. Assembly Watchdog
- **Pitch:** point a phone at a LEGO set or flat-pack build. It follows the PDF manual and warns you out loud the moment you place a wrong piece.
- **Models:** the Live API (`gemini-3.8-live`) handles voice and camera. Neon parses the manual PDF into steps with reference frames. Decision 1 runs every second: "is step N done correctly?" (`noul`) and "which piece was placed?" (`choice`). Hydrogen explains the fix. On a missing piece, the agent finds it through Shopify Catalog.
- **Demo moment:** build live in front of the judges, make a deliberate mistake, and the phone calls it out within a second.
- **Eval:** 40 recorded build clips with injected mistakes. Baseline: Neon alone on sampled frames. Metrics: mistake catch rate, false alarms and latency.
- **Risk:** needs a physical kit and good lighting. Live API is not Gemini 4, so the Gemini 4 roles must stay clear.

## 4. Fix-It Cart
- **Pitch:** film a broken household part, and the agent finds the exact replacement and puts it in a Shopify cart.
- **Models:** Neon identifies the part and its specs from video. Shopify Global Catalog returns candidates. Decision 1 picks among up to 255 candidate product images (`choice`) with calibrated confidence. Hydrogen in a managed agent checks compatibility details.
- **Demo moment:** film a judge's dead charger or a venue item, and the right product appears in the cart.
- **Eval:** 50 held-out photos of parts with known product matches. Baseline: one Neon call. Metric: correct-product rate.
- **Risk:** catalog coverage for odd parts.

## 5. Breadboard Buddy
- **Pitch:** photograph a breadboard next to its schematic, and the agent points to every miswired jumper before you power it on.
- **Models:** Neon maps the schematic PDF to a netlist. Hydrogen traces wires per region. Decision 1 votes per connection. A managed agent runs a circuit simulation in the sandbox.
- **Demo moment:** a judge moves one wire, and the overlay lights it up.
- **Eval:** 40 breadboard photos with known wiring errors. Baseline: one Neon call.
- **Risk:** needs hardware and close-up photos.

## 6. Thrift Pile to Storefront
- **Pitch:** film a pile of secondhand items, and the agent creates a priced Shopify storefront with cleaned product shots.
- **Models:** Neon segments items from video. Nano Banana 2.1 cleans the photos. Decision 1 grades condition. Hydrogen prices items from catalog comparables.
- **Eval:** price error against real sold prices for 40 items.
- **Risk:** weaker creativity score, and it drifts toward an image analyzer.

## 7. Move-In Walkthrough Report
- **Pitch:** a renter films a walk through the apartment, and the agent produces a timestamped move-in condition report with frames.
- **Models:** Neon reads long video. Decision 1 grades severity. A managed agent builds the PDF.
- **Eval:** 20 walkthroughs filmed in the venue with planted defects.
- **Risk:** could read as an image analyzer to judges.

# Round 2: ambitious, daily-life ideas

| # | Idea | Live | Proof | Creat. | Gemini | Score | Bonus prizes |
|---|---|---|---|---|---|---|---|
| A | Show Me Once | 8 | 7 | 10 | 10 | 8.55 | Managed Agents |
| B | Point and Handle It | 8 | 9 | 8 | 9 | 8.45 | Managed Agents, Shopify |
| C | Ask Your Day | 8 | 8 | 8 | 9 | 8.20 | Managed Agents |
| D | Rehearsal Room | 8 | 5 | 10 | 9 | 7.85 | none |
| E | Tour Truth (NYC apartments) | 7 | 8 | 8 | 8 | 7.65 | Managed Agents |
| F | Subway Sight | 7 | 7 | 9 | 8 | 7.60 | none |

## A. Show Me Once
- **Pitch:** film yourself doing a household task once (resetting the router, descaling the espresso machine, the building's laundry card). It turns that into a generated video manual with narration, then watches the next person live and corrects them step by step.
- **Daily life:** roommates, parents, babysitters, new hires. Anyone who asks "how do I do this again?"
- **Models:** Neon cuts the source video into steps by time interval and writes the script. `gemini-omni-1.2-flash` generates a clean clip per step from reference frames. `gemini-3.8-flash-tts` narrates in your own remixed voice. Live API watches the learner, Decision 1 answers "is step N done?" every second, and Hydrogen gives the correction. A managed agent assembles the final video and a shareable page.
- **Demo moment:** a teammate films a task, then a judge does it for the first time with the phone coaching them out loud.
- **Eval:** 15 tasks, each done by people who never saw it. Compare success rate and time against a baseline of the raw recording plus a Neon text summary.
- **Breaks first:** fine hand motions and occluded steps. Push longer source videos until step splitting fails.

## B. Point and Handle It
- **Pitch:** point your phone at any piece of real-world paperwork or a broken thing (parking ticket, utility bill, jury summons, landlord notice, a broken lamp) and say "handle this." A managed agent does the whole errand: fills the form, drafts the dispute, books the repair or orders the part, and asks before anything irreversible.
- **Models:** Neon reads the document photo and your voice note and writes a plan. Decision 1 classifies the item (`choice` over task types) and gates every irreversible step (`noul` confidence: 0.7 and above runs, 0.4 to 0.7 goes to Carbon, below 0.4 asks the human). Antigravity on Hydrogen runs computer use in the sandbox against the real or mock form. Shopify Catalog covers the "order the part" path.
- **Demo moment:** a judge hands over something from their own pocket or bag, and the agent completes the errand on screen.
- **Eval:** 40 real items from the team's own mail and photos, unseen during tuning. Score correct action plus correct form fields against a single Neon call baseline.
- **Breaks first:** handwriting, multi-page letters and sites that block bots. Use mock forms for demo safety.

## C. Ask Your Day
- **Pitch:** your phone or a clip-on camera records your day. Later you ask out loud: "Where did I leave my keys?" "What did the plumber say about the valve?" It plays back the exact clip.
- **Models:** Decision 1 is the trick: it scans thousands of frames cheaply with up to 1,000 questions per input ("are keys visible?") at $0.10 per 1M tokens. Neon reasons over the shortlisted segments with agentic video understanding. Hydrogen writes the spoken answer. A managed agent indexes footage in the background.
- **Demo moment:** record the venue for an hour in the morning, then let judges ask anything about it.
- **Eval:** 50 questions written by other attendees about 3 hours of footage. Baseline: one Neon call on downsampled video. Measure hit rate and answer time.
- **Breaks first:** tiny objects and very long footage. Push footage length until accuracy drops, and show that curve.

## D. Rehearsal Room
- **Pitch:** practice a hard real conversation (asking for a raise, disputing a bill at a counter) inside a walkable world generated from a photo of the real place, with the other person voiced live.
- **Models:** `genie-4` builds the world from your photo. Live API plays the counterpart. Neon reviews the webcam video and transcript afterward. Decision 1 scores outcomes on a negotiation rubric.
- **Risk:** proof is weak because there is no clean ground truth. Keep it to negotiation outcomes and never score personality.

## E. Tour Truth (NYC apartments)
- **Pitch:** film a broker's apartment tour or paste a listing video. The agent checks every listing claim against the footage and pulls the building's HPD violations and 311 complaints from NYC Open Data.
- **Models:** Neon checks claims against video ("renovated kitchen", "lots of light"). Decision 1 flags each claim true or false with confidence. Antigravity agent queries open data and writes the report.
- **Eval:** 30 real listings with known violations. Baseline: listing text alone.

## F. Subway Sight
- **Pitch:** a low-vision rider points the phone at a station, and it says which train, which direction and which exit, in real time.
- **Models:** Live API for voice. Decision 1 runs fast "is this the right platform?" checks. Neon reads complex signage and service-change posters. Hydrogen plans the route.
- **Risk:** safety claims will draw hard judge questions. Demo with printed signs in the venue.

# Round 3: hands-on work guided by manuals

## Why this space is strong
- **Hands are busy and eyes are on the work,** so voice and camera are the only useful interface. A text box would fail here, which is exactly what the "beyond a text box" rule rewards.
- **Manuals are visual.** Flat-pack manuals are often wordless diagrams, and service manuals mix exploded views with torque tables. A text summary loses the information that matters.
- **Mistakes have ground truth.** A panel is flipped or it isn't, a step is skipped or it isn't. That makes a clean benchmark against a baseline.
- **It fits Decision 1 perfectly.** "Is step 4 done?" and "which part is in the hand?" are yes/no and pick-one questions, answered in about 200 ms on a frame plus a diagram crop.
- **Each model gets a job set by speed.** Decision 1 answers in 0.2 s, Hydrogen in about 2 s, Neon in about 10 s and Carbon in minutes. Call this the latency ladder.

| # | Idea | Live | Proof | Creat. | Gemini | Score |
|---|---|---|---|---|---|---|
| ★ | Benchside (combines 1, 3 and 5) | 9 | 9 | 9 | 10 | 9.20 |
| 1 | Flatpack Foreman | 9 | 8 | 8 | 9 | 8.55 |
| 3 | Line Lead (factory standard work) | 8 | 9 | 8 | 9 | 8.45 |
| 5 | Expert Capture | 8 | 7 | 9 | 10 | 8.35 |
| 4 | Machine Whisperer (sight and sound) | 7 | 8 | 9 | 9 | 8.05 |
| 2 | Torque (mechanic copilot) | 6 | 7 | 9 | 9 | 7.45 |
| 6 | Lockout Verifier (safety) | 6 | 7 | 8 | 8 | 7.05 |

## 1. Flatpack Foreman
- Lay out the parts, and it inventories every panel and screw against the parts list. Then it guides each step by voice and catches the classic mistake (flipped panel, cam lock turned the wrong way) before you build five more steps on top of it.
- Clever detail: many flat-pack manuals print hardware at 1:1 scale. When two screws look alike, it asks you to lay the screw on the page and compares lengths.
- Missing part: it finds a replacement through Shopify Catalog.

## 2. Torque (mechanic copilot)
- A phone mounted under the hood. Say the job ("serpentine belt, 2014 Civic"), and it reads the service manual, points to the right bolt, reads the torque spec aloud and checks belt routing against the diagram before the engine starts.
- Hard to demo without a car. A bicycle brake or derailleur job is the portable stand-in.

## 3. Line Lead (factory standard work)
- A camera at a workstation follows the work instruction and verifies each step in order: bolts tightened in a star pattern, connector seated, label applied. It writes a traceable record per unit.
- Quality checking of the process, not just the product. Plants care about this a lot.

## 4. Machine Whisperer (sight and sound)
- Film a machine that is acting up. It listens to the sound (squeal, knock, grind), reads the error code on the panel, walks through the manual's troubleshooting table, and asks you to show it specific parts.
- Audio is the core input, and a text description loses it. Works for home appliances too.
- Possible eval data: public industrial machine sound datasets with labeled faults (check the license first).

## 5. Expert Capture
- A senior technician does a repair once while narrating. The agent produces an interactive work instruction with generated step clips, then coaches new hires live.
- Pain point: experienced workers retire and their know-how leaves with them.

## 6. Lockout Verifier (safety)
- Before maintenance, it visually confirms each lockout and tagout step: lock on the breaker, tag attached, zero-energy check done.
- High value, but safety claims draw tough judge questions.

## ★ Benchside: the combined pitch
- **Pitch:** any manual in, a live camera-checked procedure out. One engine runs three modes: Assemble (furniture), Run (factory work instruction) and Capture (an expert records once). The live hero demo is a real chair.
- **Manual ingest (managed agent):** Antigravity on Neon turns the PDF into a step graph: parts list, hardware, expected state per step, diagram crops and known mistakes. Carbon audits the graph once.
- **Live loop:** the browser camera sends a frame every second. Decision 1 asks 3 to 10 questions per frame against the diagram crop for the current step. Voice comes through the Live API, or browser speech as a fallback.
- **Escalation:** confidence from 0.4 to 0.7 goes to Hydrogen with frame plus diagram. If it stays low, Neon gets the last 10 seconds of video. Below 0.4 it asks the user to show the part closer.
- **Actions:** order the missing part on Shopify, then write a job record with photos per step.
- **Eval (mistake-injection benchmark):** about 40 short clips of steps done right and wrong (flipped panel, wrong screw, skipped step), performed by attendees outside the team. Baseline: one Neon call per frame with the manual pages. Metrics: catch rate, false alarms, latency and cost per hour. Generalization check: run manual ingest on 3 manuals (chair, bike brake, 3D printer nozzle swap).
- **Breaks first:** hands blocking the view, look-alike screws and bad light. Fixes: ask for a closer shot, use the 1:1 scale page and add a light check.

# Round 4: autonomous managed agents, no step-by-step coaching

Shape: the user hands over media once (a URL, a video, a pile of photos). A fleet of managed agents works in parallel sandboxes, produces media of its own, and comes back with finished work. Nobody goes back and forth with it.

| # | Idea | Live | Proof | Creat. | Gemini | Score | Bonus prizes |
|---|---|---|---|---|---|---|---|
| A | QA Swarm | 9 | 9 | 8 | 10 | 9.00 | Managed Agents, Shopify variant |
| B | Watch Me Work | 8 | 9 | 8 | 9 | 8.45 | Managed Agents |
| C | Ask the Building | 8 | 8 | 8 | 9 | 8.20 | Managed Agents |
| D | Product Film Studio | 8 | 6 | 9 | 10 | 8.10 | Shopify, Managed Agents |
| E | Shoebox Accountant | 7 | 9 | 6 | 8 | 7.50 | Managed Agents |
| F | First-Visit Dispatch | 7 | 6 | 8 | 9 | 7.35 | Shopify |

## A. QA Swarm
- **Pitch:** paste any web app URL plus a 30-second screen recording of the main user flow. Twenty managed agents, each playing a different persona, test it at the same time and come back with ranked bug reports, each with a video clip and a repro script.
- **Personas:** screen-reader user, phone on slow 3G, chaotic clicker, non-English speaker, keyboard only, and more.
- **Models:** Neon watches the reference recording and writes a test plan per persona. Antigravity on Hydrogen runs each persona in its own sandbox with Playwright and computer use, recording video. Neon reviews every session video for broken or confusing moments. Decision 1 dedupes across the 20 videos ("same bug as #3?") and scores severity. Carbon writes the final report on the top bugs.
- **Demo moment:** ask a judge for another team's hackathon URL and return a bug report with clips within 3 minutes.
- **Eval:** a demo app with 25 seeded bugs. Baselines: one agent with no personas, and an off-the-shelf accessibility checker. Metrics: bugs found, false reports and time.
- **Shopify variant:** Mystery Shopper Swarm. Agent shoppers go through a Shopify dev store checkout and report what would make a real customer leave.
- **Risk:** sandbox startup time with 20 in parallel. Pre-warm, or cap at 8 for the live run.

## B. Watch Me Work
- **Pitch:** record yourself doing a boring web task once (expense filing, copying rows between two sites). The agent turns the video into a working automation, proves it by replaying it, then runs it on 100 rows in parallel.
- **Models:** Neon turns the video into a script by time interval. Antigravity on Hydrogen writes and runs the Playwright script in the sandbox. Decision 1 compares frames of its replay against your recording ("same screen state?") to verify. Carbon fixes scripts that fail.
- **Eval:** 20 tasks on self-hosted test sites. Baseline: an agent given a typed description of the task instead of the video.

## C. Ask the Building
- **Pitch:** several phones around the venue stream at once. Ask out loud "where did I leave my laptop charger?" or "when did the pizza arrive?" and get the clip from the right camera.
- **Models:** Decision 1 scans every stream cheaply (1,000 questions per input). Neon reasons over shortlisted clips. Managed agents index each stream in parallel.
- **Pushes:** more streams at once and longer footage. That matches the Element 119 prompt directly.

## D. Product Film Studio
- **Pitch:** shoot a 20-second phone clip of a product. A fleet of agents makes studio photos, a 15-second ad with music and voiceover, and the listing, then publishes it all to a Shopify store.
- **Models:** Nano Banana 2.1 for photos, Omni 1.2 for the ad, Lyria 3.5 for music, TTS for voiceover, Neon writes the listing. Decision 1 acts as art director and scores each candidate against a brand rubric to pick the best.
- **Risk:** proof is soft. The best option is a blind preference test with attendees.

## E. Shoebox Accountant
- **Pitch:** dump 200 photos of receipts, bills and voice memos. Parallel agents sort them, match them against a bank export in the sandbox, and return a tax-ready spreadsheet.
- **Eval:** accuracy against hand-labeled receipts. Strong proof, less wow.

## F. First-Visit Dispatch
- **Pitch:** a customer sends a 30-second video of a broken appliance. Agents diagnose from sight and sound, find the part on Shopify, write a quote and send the right technician with the right part on the first visit.
- **Risk:** hard to find labeled fault videos for the eval.

# Round 5: five domain scouts, no Shopify (1:10 PM)

| Idea | Domain | Score | One line |
|---|---|---|---|
| Doorway | Creative | 8.50 | Walk inside an old family photo as a live Genie 4 world, steered by a relative's recorded story |
| Rain Witness | Wild card | 8.45 | Agents watch NYC street cameras and map rain block by block (weather dependent) |
| Safe Word | Civic | 8.25 | Emergency briefing video becomes checked audio and alert cards in 5 languages, catching dropped facts |
| Tape Desk | Field work | 8.25 | Raw press-conference video becomes a fact-checked package, evaluated on PolitiFact rulings |
| Promise Ledger | Civic | 8.20 | Hours of City Council video become a list of official commitments with clips and follow-through checks |
| Cue | Creative | 8.10 | A live score for improv theater that turns when the scene turns |
| Lost Reel | Creative | 8.10 | Regenerate the seconds a damaged home movie lost |
| Night Shift Naturalist | Wild card | 8.05 | Six hours of a wildlife livestream become a behavior log and a narrated 60-second reel |
| Nightshift | Civic | 7.95 | Record late-night construction noise, check it against after-hours permits |
| Exit Drill | Home | 7.90 | A 60-second home video becomes a checked fire escape plan plus a playable drill world |
| Hum Court | Wild card | 7.90 | Hum 15 seconds, 20 Lyria covers, a verifier panel rejects any that lost the melody |
| Hum | Home | 7.80 | Record a noisy appliance, hear which part is failing |
