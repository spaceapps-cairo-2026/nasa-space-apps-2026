# Research brief (compiled Fri 13 Nov 2026, 02:00 Cairo)

Verify anything marked VERIFY against the official site at kickoff. The official challenge pages block automated reading, so the list below comes from local event sites that mirror it.

## 1. Key facts

- Event: NASA Space Apps Challenge 2026, theme "The Next Frontier", Sat 14 and Sun 15 Nov 2026.
- Submission opens Sat 14 Nov 09:00 and closes Sun 15 Nov 23:59 local time. That is about 39 working hours, not 48.
- Team size: max 6.
- The project must respond to one official challenge. "Create Your Own Challenge" projects are not eligible for Global Judging.
- Submission page and linked material must be in English. The demo video can be in Arabic only if it has English subtitles.
- All external resources (code, text, images, datasets) must be listed in the References field, even if open source.
- No recognizable names, voices, or faces of anyone under 18 in videos or submissions.
- Space Apps has no official "AI/ML track". Cairo may group challenges into local tracks. VERIFY at kickoff which challenges count for the Cairo AI/ML track.
- AI tools: the 2026 judging guide found online has no AI specific rule. Safe practice: list "Claude (Anthropic), used for code assistance and drafting" in References. VERIFY the 2026 Project Submission Guide (released 13 Nov).

Sources: spaceappschallenge.org/2026, /resources/judging-awards-guide, /resources/participant-faqs.

## 2. How judging works

1. Local judges (Cairo) pick Global Nominees, roughly 1 per 10 projects submitted.
2. NASA and partner experts pick Global Finalists and Honorable Mentions (December).
3. NASA executives pick 10 Global Winners (January 2027).

### The five criteria (equal weight)

| Criterion | What judges ask | How we win it |
|---|---|---|
| Influence | How big is the problem, how many people does it help | Name a real user and a real number (farmers, mission planners, fire agencies) |
| Creativity | New approach or incremental | One idea nobody else in the room has; not "a dashboard of dataset X" |
| Validity | Scientifically sound, achieves its goal, works in the real world | Baseline vs model table, honest validation split, one known event reproduced |
| Relevance | Answers the challenge, complete, feasible, usable | Map every bullet of the challenge statement to a feature |
| Presentation | Did they communicate problem, solution, why it matters | Story first, demo second, numbers third. The guide explicitly warns teams under-invest here |

### The 10 global awards
Best Use of Science, Best Use of Data, Best Use of Technology, Galactic Impact, Best Mission Concept, Most Inspirational, Best Storytelling, Global Connection, Art and Technology, Local Impact.

For an AI team the natural targets are **Best Use of Data**, **Best Use of Technology**, and **Best Use of Science**. **Local Impact** is a strong secondary angle for an Egypt focused project.

## 3. The 14 challenges for 2026

| # | Challenge | Level | ML fit |
|---|---|---|---|
| 1 | Abandoned but not Forgotten (story of hardware left on Moon/Mars) | Beginner/Intermediate | Low |
| 2 | Be An Earth System Trend Detective! (are Earth changes over time meaningful) | Advanced | HIGH: trend + significance testing, anomaly detection |
| 3 | Build a Junior Astronaut Mission Trainer (game) | Beginner/Intermediate | Low |
| 4 | CLPS Lunar Mission Browser (sunlight + comms windows at lunar south pole) | Advanced | Medium: mostly geometry/visualization |
| 5 | Create Health Monitoring Software for Astronauts | Intermediate | Medium/High: anomaly detection on physiological signals |
| 6 | Dancing with the SARs (NISAR radar, visualize surface change) | Advanced | HIGH: change detection, but heavy data |
| 7 | Field Shift: Adapting Farms with NASA Data (resilient crop rotations) | Advanced | HIGH: decision support + Egypt local impact |
| 8 | Flame in Freefall: AI-Powered Fire Safety Insights from Microgravity Combustion Data | Advanced | HIGH: explicitly asks for AI (likely retrieval/RAG over experiment records + modeling) |
| 9 | Harmonization of MODIS and VIIRS Hot Spots (one consistent fire calendar) | Advanced | HIGH: cross-sensor calibration, classic ML regression |
| 10 | Identify Earth Locations that Analog Moon/Mars Bases | Advanced/Intermediate | HIGH: similarity search / clustering; Egypt's deserts are famous analogs |
| 11 | Interplanetary Survival Guide: Martian Map (layered map for safe routes) | Intermediate | Medium: path planning on cost maps |
| 12 | Planet X and SPHEREx (find moving or changing objects in sky images) | Advanced | HIGH: computer vision, but steep astronomy learning curve |
| 13 | Space Mission Design Game | Intermediate | Low |
| 14 | The Earth Information Jukebox (sonification) | Intermediate | Low/Medium |

Sources: nasaspaceapps.lk/challenges, nepvents.com, spaceappschallenge.ch.

## 4. What past winners did (patterns we can copy)

2025 Global Winners (from NASA's announcement):
- **Best Use of Data, Resonant Exoplanets (USA):** AI system that scans large telescope datasets (incl. JWST spectra) for exoplanets and possible biosignatures.
- **Best Use of Technology, Twisters (Mexico):** "SkySense" web app combining NASA Earth observation + AI into hyperlocal forecasts, risk scores, and suggested safe time windows.
- **Best Use of Science, SpaceGenes+ (Germany):** interactive dashboard on how radiation + microgravity affect astronauts at the molecular level, framed as a decision aid for mission planners.
- **Galactic Impact, Astro Sweepers (Universal):** public orbital data turned into debris compliance reports and a risk index.
- **Art and Technology, Zumorroda-X (EGYPT):** mini games teaching how farmers adapt to heat waves and floods with NASA data.
- **Local Impact, QUEÑARIS (Peru):** satellite data + drones + AI for reforestation site selection, tied to a named local water crisis.
- Cairo produced a Global Winner in 2024 (Best Storytelling) and in 2025 (Art and Technology).

Patterns:
1. **Turn data into a decision.** Winners output a risk score, a time window, a recommended site, a report. Not "here is a map of the data".
2. **One named user.** Mission planner, farmer, researcher, child in a classroom.
3. **AI is a means, not the headline.** The headline is the outcome; AI explains how.
4. **Show it working.** A 2023 winner said they won because everything was built and demoable. In 2024, five of the final 40 teams built the same kind of app (orreries), so being different matters.
5. **Local angle wins locally.** Egyptian teams that won globally used local stories (farmers, heat).
6. **Polish and story.** Both Cairo global winners won presentation-heavy awards.

## 5. Open questions for kickoff (VERIFY)
- Cairo schedule: when is the local pitch, is there an earlier local submission deadline, pitch length, live demo or video?
- Which challenges count for the Cairo AI/ML track?
- Exact demo video length limit in the 2026 Project Submission Guide.
- Any 2026 rule on generative AI disclosure.

## 6. Our challenge: competition analysis (searched 13 Nov)

Many teams worldwide published repos for this challenge weeks before the event (statements came out 28 Oct). What they built:
- 3D globes of the whole world with many variables (the most common entry by far).
- Mann-Kendall + Sen's slope, often with FDR correction. Some with autocorrelation correction and validation against GISTEMP and NSIDC sea ice.
- "AI detective" reports written by a language model.
- Country focus entries (mostly Bangladesh), plus niche angles (ship routes, methane).

So "a globe with Mann-Kendall" will NOT stand out. What should:
1. **Depth over breadth:** one country, 1 km satellite pixels, places a judge can see on a satellite image.
2. **The statement's own twist, made visible:** opposite trends from one process (adding Nile water vs building over farmland), found automatically by the fingerprint model.
3. **"When did it start"** via change points, which almost nobody shows.
4. **Honest statistics as a feature:** show how many "trends" disappear with autocorrelation + FDR, and where our method fails.
5. **Local impact:** Egypt's water and food security story.

## 7. Rules check
- The 2024 FAQ: "At 9:00 a.m. (local time) teams may begin working on their hackathon projects." Before that: form team, pick challenge, plan, gather data, choose tools. We keep product code for Saturday.
