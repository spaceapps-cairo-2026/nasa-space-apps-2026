# Game plan: Sat 14 and Sun 15 Nov 2026 (Cairo time)

Nothing guarantees first place. This plan removes the usual ways strong teams lose: picking late, data that never arrives, integration chaos, no sleep, and a weak pitch.

## What we will face

| Problem | When it hits | Our answer |
|---|---|---|
| 14 challenges, endless debate | Sat morning | Decision matrix, hard deadline 10:30 |
| Data downloads slow, need logins, are huge | Sat 11:00 to 15:00 | Earthdata account made tonight; small slice only; cache everything |
| Waiting on each other | All day Sat | Lanes + contract + fake data: nobody waits |
| Merges break things at night | Sat night | Only lane A merges, at fixed times, tests must pass |
| Claude usage limit hit mid task | Any time | `/handoff`, continue on another account or claude.ai chat |
| Venue Wi-Fi dies | Any time | App libraries bundled; data cached; phone hotspot as backup |
| Exhaustion, bad decisions at 4 AM | Sun 02:00 to 08:00 | Sleep in shifts, no new features at night |
| Demo breaks on stage | Pitch | Recorded backup video + screenshots in the slides |
| Weak story, judges confused | Pitch | Story spine in PITCH.md, rehearsed 3 times |
| Late submission panic | Sun night | First submission at 20:00, then only improve |

## The schedule

### Tonight (stop by 03:00)
1. Run the setup command (see README) on Mohammed's laptop. Friend clones the repo and runs `python run.py setup` and `python run.py check`.
2. Everyone: free NASA Earthdata Login account at urs.earthdata.nasa.gov. One person: FIRMS MAP_KEY (firms.modaps.eosdis.nasa.gov/api/map_key) in case we pick the fire challenge.
3. Test `.\scripts\second_account.ps1 lane/b-app` once.
4. Charge laptops, power banks, phone hotspot data. Sleep.

### Challenge already chosen: Be An Earth System Trend Detective
Friday is for data gathering (AppEEARS request, POWER download) and reading CHALLENGE.md / METHODS.md.
The hour-by-hour task list for this challenge is in TASKS.md; the timeline below still applies.

### Sat 09:00 to 11:00: kickoff + engine first
- Confirm at kickoff: Cairo pitch time and format, local deadline, live demo or video.
- Lane A starts the trend engine on POWER data (already downloaded). Lane B starts the map on fixtures v0.2. Lane C checks AppEEARS.

### Sat 11:00 to 20:00: walking skeleton (real data, end to end, ugly is fine)
- Lane C: smallest real data slice into `data/processed/features.parquet` by 14:00.
- Lane A: baseline model on the slice, an honest time or region split, and a metric.
- Lane B: the app shows the challenge's real fields, still on fake data.
- **14:00 checkpoint:** no real data yet means cutting scope (smaller region, fewer years). Do not switch challenge.
- **17:00:** talk to a mentor. Ask: "What would make a judge here remember this project?"
- **20:00 integration:** everything merged, `python run.py check` green, the app shows REAL predictions. Deploy once now (Render or Hugging Face Spaces) to surface deploy problems early.

### Sat 20:00 to Sun 02:00: make it good
- Lane A: beat the baseline, add a per-item explanation of "why this score", and fill the model card table.
- Lane B: one hero screen that tells the story in 10 seconds. Loading states. No new pages.
- Lane C: validation against one real, known event (e.g. "our model flags X on date Y; here is what actually happened"). This is the strongest Validity evidence there is.

### Sun 02:00 to 08:00: sleep in shifts
- Two people sleep 02:00 to 06:00, one person runs long jobs, writes docs, and takes screenshots. Then swap.
- Usage limits recover overnight. Plan heavy Claude work for the morning.

### Sun 08:00 to 14:00: final features
- Polish only what appears in the demo path.
- **14:00 FEATURE FREEZE.** After this, bug fixes only.

### Sun 14:00 to 23:59: story and submission
- 14:00 to 17:00: demo video. Follow PITCH.md's spine, English subtitles, a scripted click path.
- 17:00 to 19:00: slides plus the submission page: title, summary, the challenge mapping, a public repo link, and the full references list including the AI tools.
- **20:00: SUBMIT version 1.** Then improve until the deadline.
- Rehearse the live pitch 3 times with a timer. Every teammate can answer "how did you validate it?"
- Make the GitHub repo public before final submission.

## How we score on each judging criterion

| Criterion | Concrete thing we show |
|---|---|
| Influence | "X people in Egypt / N mission planners face this; today they decide by Y" |
| Creativity | One sentence: "Unlike existing tools, we ___" |
| Validity | Baseline vs model table + one real event reproduced + stated limitations |
| Relevance | Slide with each challenge objective, each with a checkmark and the feature that answers it |
| Presentation | Hook with a real moment, live demo, backup video, under time |

## Rules for the AI accounts
- Every session starts with `/sync`, ends with `/handoff`.
- Use Claude Code for code. Use claude.ai chat for reading statements, the pitch, and video scripts, which saves Claude Code usage.
- Ask Claude to write tests for anything in `contracts/` before changing it.
- If a Claude session loops on the same bug for 20 minutes: stop, `/handoff`, fresh session with a smaller ask.
- Humans decide scope. Claude never adds features not in CHALLENGE.md.
