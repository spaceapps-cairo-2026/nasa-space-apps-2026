# Task board

What we build and why: `PROJECT_PLAN.md`. This file is **who does what, and in which order**.

## How to use this board

- **Claim** a task: replace `owner: ___` with your name, commit, push. Only claim tasks in a lane you are working in.
- **Tick** it when done: `[x]`, and add one line to `docs/LOG.md`.
- **needs:** lists the tasks that must be merged to `main` first. A task with `needs: none` can start right away.
- **Never blocked:** a task whose `needs` is a contract (A1, A2) can start on the fixtures in `contracts/fixtures/` before the real data exists. Build on fake data, switch to real data later.
- Each lane edits **only its own section** below, so ticks never cause merge conflicts. Need something from another lane? Add a `REQUEST:` line to that lane's inbox at the bottom.
- Telling Claude to do a task: `/sync`, then for example `Do task B3 from TASKS.md`.

## What runs in parallel and what waits

**Start together at Sat 09:00 (nobody waits for anybody):**
A1, A3, B1, B5, C1, C2, C3, C4. Lane A merges A1 and A2 into `main` as soon as each is ready (not at the next merge point), so all of lane B's screens can be built on fixtures by about 10:30.

**Chains that must happen in order (coordinate these):**
1. **F1 trends:** A1 contract + A3 method choice (D1, D2) → A4 trend engine → **13:00 merge** → C5 validation, C6 pitch numbers
2. **Live point:** C1 point fetch + A4 trend engine → B4 real `/trend/point`
3. **Crops:** C3 crop table (D6) → A6 crop engine → A7 projections → A8 decision rankings
4. **Farmland:** A4 trend engine → A5 viability score (D4) → A7 projections
5. **App:** B1 globe library (D3) → B2 globe + selection → B10 guided tour (needs C7 tour script)
6. **Story:** all features frozen (Sun 14:00) → C8 video and slides → submission

**Merge points** (lane A merges green pull requests, then everyone runs `/sync`): Sat 13:00, Sat 20:00, Sun 02:00, Sun 10:00, Sun 14:00 freeze.

## Phase 0: Friday (now), preparation only, no product code

- [x] (all) GitHub org, private repo, lane branches, CI check
- [ ] (all) Read `PROJECT_PLAN.md` and this file; send questions to the group tonight
- [ ] (all) Accept the GitHub invite, run the one line join command, `python run.py check` green on every laptop
- [ ] (C) Paste the official challenge Resources tab into `docs/DATA.md` section 0
- [ ] (C) Collect FAO ECOCROP data sheets for the candidate crops (`PROJECT_PLAN.md` F3)

## Lane A: analysis + integration (`ml/`, `contracts/`)

- [ ] **A1** Contracts for F1: point trend and region trend JSON shapes, fixtures, endpoints in `contracts/api.md`, and the Python signature of the trend function the API calls | needs: none | owner: ___
- [ ] **A2** Contracts + fixtures for F2 viability, F3 crops (both modes, irrigated and rain-fed), F4 decisions, so lane B can build every tab on fake data | needs: A1 | owner: ___
- [ ] **A3** D1 + D2: compare trend and confidence methods on the Egypt grid, pick one, set confidence levels and wording (with C), write it in `docs/DECISIONS.md` | needs: none | owner: ___
- [ ] **A4** Trend engine: region trends for Egypt to `ml/outputs/`, plus the point function for live requests | needs: A1, A3 | owner: ___
- [ ] **A5** D4: farming viability score per cell per year, its trend and confidence | needs: A4 | owner: ___
- [ ] **A6** Crop suitability per cell per year, rain-fed and irrigated | needs: C3, A2 | owner: ___
- [ ] **A7** D5: projections for +5 and +10 years with uncertainty, labeled "if current trends continue" | needs: A5, A6 | owner: ___
- [ ] **A8** Decision rankings for investors and planners (every row links to its evidence) | needs: A7 | owner: ___
- [ ] **A9** Merge points: merge green PRs at each merge time; Sun 10:00 freeze all numbers; final tests green | needs: none | owner: ___

## Lane B: API + app (`api/`, `app/`)

- [ ] **B1** D3: choose globe and map libraries, bundle them into `app/vendor/` (must work offline except map tiles) | needs: none | owner: ___
- [ ] **B2** F0: globe, country/city search, click a point, fly to the area, outline it, pass the selection to every tab | needs: B1 | owner: ___
- [ ] **B3** F1 Trends tab on fixtures: measurement picker, time series chart with trend line, rate per decade, confidence label, region map with "not proven" in grey, plain sentence | needs: A1 | owner: ___
- [ ] **B4** API: `/trend/point` and `/trend/region` on fixtures (`MOCK=1`), then real data; "regional analysis available for: Egypt" outside Egypt | needs: A1 (real: A4, C1) | owner: ___
- [ ] **B5** Methods page layout (F5); text and validation numbers come later from A and C | needs: none | owner: ___
- [ ] **B6** Farmland tab (F2): gaining / losing / stable map, horizon selector (now, +5, +10), "crossing" highlight, projection label | needs: A2 | owner: ___
- [ ] **B7** Crops tab (F3): mode A crop to places, mode B place to crops, irrigation toggle | needs: A2 | owner: ___
- [ ] **B8** Decisions tab (F4): investor and planner lists, each row opens the map and evidence | needs: A2 | owner: ___
- [ ] **B9** D9: hosting; first deploy by Sat 20:00 | needs: B2, B3, B4 | owner: ___
- [ ] **B10** Guided tour (F6): one button plays the story end to end, from cached data | needs: B2 to B8, C7 | owner: ___

## Lane C: data + science + story (`data/`, story docs, `demo/`)

- [ ] **C1** POWER point fetch for any lat/lon (`T2M_MIN` added) with a local cache in `data/cache/` | needs: none | owner: ___
- [ ] **C2** GISTEMP global means: download script and tidy table for validation | needs: none | owner: ___
- [ ] **C3** D6: final crop list (8 to 12) and how irrigation is modeled; `data/crops/crops.csv`, one row per crop with its source link | needs: none | owner: ___
- [ ] **C4** `docs/REFERENCES.md`: every dataset, library and AI tool, kept current all weekend | needs: none | owner: ___
- [ ] **C5** Validation (F5): reproduce the GISTEMP rate with our engine, check one known real change, write the limitations | needs: A4, C2 | owner: ___
- [ ] **C6** Pitch draft in `docs/PITCH.md` with real numbers | needs: A4 | owner: ___
- [ ] **C7** Demo script: the tour story step by step and the list of points to cache for it | needs: B6, B7, B8 roughly working | owner: ___
- [ ] **C8** Demo video with English subtitles, and slides | needs: feature freeze (Sun 14:00) | owner: ___
- [ ] **C9** (P2, only if time) D7: download POWER grids for 1 or 2 more countries | needs: none | owner: ___
- [ ] **C10** (P2, only if time) MODIS evidence layer via AppEEARS | needs: none | owner: ___

## Everyone, Sunday

- [ ] Submission page text, references complete (data, libraries, AI tools used)
- [ ] Make the repo public; **submit by 20:00**; improve until 23:59

## Lane A inbox

## Lane B inbox

## Lane C inbox
