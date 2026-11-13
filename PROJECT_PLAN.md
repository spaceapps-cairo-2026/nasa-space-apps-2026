# PROJECT PLAN: CropShift Earth (working name)

NASA Space Apps 2026 Cairo, challenge "Be An Earth System Trend Detective!"
This file is the **single source of truth** for what we build. Every Claude session reads it first, together with `CLAUDE.md`.
It defines **what** we build and **who** builds it. It deliberately does **not** fix the algorithms; those are decided during the hackathon (section 9).

---

## 1. The product in one paragraph

A 3D Earth where anyone can fly to a country, a city, or any point, pick a NASA measurement (temperature, rain, soil moisture, humidity...) and see **how it has changed since 2001, how fast, where, and how confident we are that the change is real and not normal year to year variation**. On top of that, the app turns those trends into **farming decisions**: which land is becoming **more or less viable for farming**, which **crops** fit a place **today and in 5 or 10 years if current trends continue**, and what that means for **investors** (where to buy, where to exit) and **governments** (which farming areas are under growing stress, which are gaining potential).

## 2. The challenge requirement (must be visible in the demo)

The official statement asks for a tool that can:

| # | Requirement | Our feature |
|---|---|---|
| R1 | Select variables measured by NASA missions or produced by NASA models | F1 measurement picker |
| R2 | Visualize how they change over time | F1 time series chart with trend line |
| R3 | Determine **what** is changing | F1 variable + direction label |
| R4 | Determine **where** it is changing | F1 trend map over the chosen region (not only one point) |
| R5 | Determine **how much** it is changing | F1 rate of change in real units per decade |
| R6 | Determine if the change is **significant** | F1 confidence label per place, "not proven" when it could be normal variation |
| R7 | (Statement's twist) a variable can trend one way in one region and the opposite way in another from the same process | F2/F3 maps show gains and losses side by side, called out in the demo |

**Wording rule for R6.** A significance test does NOT give "the probability the trend is true". It gives how likely a trend this strong would appear if nothing were really changing. So the app shows **confidence levels** (for example: strong evidence / moderate evidence / not proven), with the exact number available on hover. Never display "87% true".

## 3. Users and the decision each one makes

| User | Question | Feature |
|---|---|---|
| Student, journalist, curious citizen | "Is my city really getting hotter or drier?" | F1 |
| Farmer / agricultural investor | "Which land should I buy or leave? What should I plant?" | F2, F3, F4 |
| Government planner (agriculture, water, land) | "Which farming regions are under growing climate stress, which are gaining potential, where to prepare support?" | F2, F4 |

## 4. User journey (screens)

1. **Globe.** 3D Earth. Search box (country or city) or click anywhere.
2. **Area selection.** Whole country, a city (radius), or a single point. The camera flies there; the area is outlined.
3. **Mode tabs** for the selected area:
   - **Trends** (F1): pick a measurement, see map + chart + numbers + confidence.
   - **Farmland** (F2): pick a time horizon (now, +5 years, +10 years), see land becoming more / less viable.
   - **Crops** (F3): pick a crop and a horizon, see where it fits; or click a place and see its best crops.
   - **Decisions** (F4): ranked lists for investors and planners.
4. **Methods** page (F5): how we compute, how we validated, limitations.
5. **Guided tour** (F6): a 60 second scripted story for the demo and the video.

## 5. Features, priorities and "done" criteria

Priority: **P0** = must exist for submission. **P1** = should exist (this is our edge). **P2** = only if time remains.

### F0. Globe and place selection (P0)
- 3D globe, rotate and zoom, country borders.
- Search by country or city name; click any point.
- Selection types: country, city (with radius), point.
- Smooth transition from globe to a regional map view for detail.
- **Done when:** a user can reach Cairo, Egypt, or any clicked point in under 3 interactions, and the selected area is passed to every mode.

### F1. Trend explorer: the official objective (P0)
- Measurement picker: at least air temperature, max temperature, precipitation, soil moisture, humidity.
- For a **point or city**: time series 2001 to 2025, trend line, rate per decade in real units, confidence label, start year of change if detected (P1).
- For a **country / region, anywhere in the world**: map of every grid cell colored by trend direction and size; cells without convincing evidence shown as "not proven" (grey). Zoomed out, the whole globe is colored the same way.
- Works for **the whole world** by **live fetch**: when a user selects a country or region, the app fetches its NASA POWER data on the spot, keeps it on disk, and computes the trend map. A single point or city is fetched live the same way. Nothing must be downloaded in advance.
- Plain language sentence generated only from computed numbers, e.g. "Since 2001, average temperature here rose by 0.3 C per decade. Strong evidence this is a real change."
- **Done when:** R1 to R6 are all visibly answered for Cairo, for one random point outside Egypt, and the trend map works for Egypt and for at least two countries on other continents.

### F2. Farmland viability change (P1, our core edge)
- A **farming viability score** per place per year, built from the measurements (definition decided in section 9).
- Map for the selected region: land that is **gaining** viability, **losing** viability, **stable**, with the same confidence rules as F1.
- Time horizon selector: **now**, **+5 years**, **+10 years**. Future views are **projections that assume current trends continue**, always labeled as such, with an uncertainty indicator.
- "Crossing" highlight: places expected to **switch** from viable to not viable (and the reverse) within the chosen horizon.
- **Done when:** for Egypt, the map shows gaining and losing areas, the horizon selector changes the map, and every future view carries the projection label.

### F3. Crop suitability (P1)
- Crop picker with a curated list of about 8 to 12 crops that have published requirements (candidates: wheat, maize, rice, cotton, potato, tomato, citrus, mango, date palm, olive, grape, avocado, apple). Final list decided in section 9.
- **Mode A, crop to places:** pick crop + horizon (now / +5 / +10), see where it is suitable inside the selected region, and where suitability is rising or falling.
- **Mode B, place to crops:** click a place, see crops ranked by suitability now and at the chosen horizon, with which ones are improving or declining.
- **Irrigation toggle:** "rain-fed" vs "irrigated" (irrigated ignores rainfall limits). Essential for Egypt, where most farming is irrigated.
- **Done when:** for at least 8 crops, both modes work for Egypt, and the irrigation toggle visibly changes results.

### F4. Decision views (P1)
- **Investor view:** ranked list of areas in the region: "best to acquire for crop X by horizon Y", "highest risk of losing viability". Each row links to the map and the evidence.
- **Planner view:** areas with significant declining viability (where farmers may need support, adaptation or relocation help) and areas with significant rising viability (where new farming capacity could be prepared).
- Export of the ranked list as CSV (P2).
- Wording is advisory ("signals for planning"), never instructions; every item shows its confidence level.
- **Done when:** both lists exist for Egypt and every row can be traced back to its trend evidence.

### F5. Methods and validation page (P0)
- Plain language explanation of trend, rate, confidence, projection.
- Validation results: at least one published NASA number reproduced by our engine, and one known real world change shown correctly.
- Limitations listed honestly (grid resolution, irrigation, projections are not forecasts, no soil data if absent).
- **Done when:** a judge can read it in 2 minutes and trust the numbers.

### F6. Guided demo tour (P1)
- One button plays the story: globe, then Egypt warming (F1), then farmland gains and losses (F2), then one crop example (F3), then decision list (F4).
- **Done when:** the tour runs end to end without the presenter touching anything else.

### Explicitly OUT of scope
- Daily or hourly weather forecasts. Soil chemistry, pests, market prices, water rights. Claims about causes ("caused by"). User accounts. Mobile app. Every country in full regional detail.

## 6. Geographic scope

**Trends are worldwide. Farming features are for chosen countries.** (Team decision, Fri 13 Nov.)

| Feature | Where it works | How |
|---|---|---|
| F1 trend for a point or city | anywhere on Earth | fetched live from NASA POWER (about 1.3 s per point, no login) |
| F1 trend map | **the whole world**, any country or region | **live fetch with a local cache**: `region_monthly()` in `data/power_world_fetch.py` gets the 10 x 10 degree tiles covering the selection (first time: about 5 to 40 s depending on size; after that instant) |
| F1 globe overview (whole Earth colored at once) | whole world | temperature is precomputed and in the repo (`data/processed/world/T2M_annual.npz`); other measurements only if the optional bulk download (`python run.py world`) has finished |
| F2 farmland, F3 crops, F4 decisions | **focus countries only**: Egypt first, more chosen in D7 | precomputed per country; needs country specific care (irrigation, crop list) |

- Outside the focus countries, the Farmland, Crops and Decisions tabs say "farming analysis available for: Egypt" instead of failing. The Trends tab always works.
- **Speed rule:** the first request for a new region waits for NASA, so the app shows a loading message ("fetching NASA data for this region..."). Everything used in the demo and the tour is fetched once beforehand, so the demo runs from the local cache.
- **Big selections:** a very large country (Russia, Canada, USA) covers many tiles. The app asks the user to zoom in, or uses the precomputed temperature layer.
- **Map delivery:** a region has hundreds to thousands of cells, so lane A ships a trend map as a compact grid (rate + confidence per cell), not one JSON object per cell. The exact shape is part of task A1.
- Over the ocean, soil wetness does not exist and is shown as "no data"; temperature, rain and humidity trends are valid there.

## 7. System skeleton

```
NASA POWER (live point API + precomputed grids)     Crop requirements (FAO ECOCROP)
              |                                                  |
              v                                                  v
 data/       fetch + cache + tidy tables  ------------------>  data/crops/ (curated table)
              |
              v
 analysis/   trend engine        (rate, confidence, change start)      <- decided in section 9
             viability engine    (farming viability score per year)    <- decided in section 9
             crop engine         (suitability per crop per year)       <- decided in section 9
             projection engine   (now / +5 / +10 under current trends) <- decided in section 9
              |
              v
 outputs/    precomputed JSON per region (contracts/ define shapes)
              |
              v
 api/        FastAPI: /trend/point, /trend/region, /viability, /crops, /decisions, /meta
              |
              v
 app/        globe + regional map + charts + mode tabs + methods page + tour
```

Folder mapping in this repo:

| Folder | Content | Lane |
|---|---|---|
| `data/` | download scripts (POWER grid done, POWER point to add), crop table builder | C |
| `ml/` (analysis) | trend, viability, crop, projection engines; writes `ml/outputs/` | A |
| `contracts/` | JSON shapes between analysis, API and app; fake fixtures | A owns |
| `api/` | endpoints serving `ml/outputs/` and live point trends | B |
| `app/` | globe, maps, charts, tabs, methods page, tour | B |
| `docs/` | plan, data notes, methods, pitch, references | C (A for methods) |
| `tests/` | contract tests, engine sanity tests | everyone |

**Contract first.** Before building each feature, lane A adds its JSON shape and a fake fixture in `contracts/`, so lane B builds the UI on fake data while lane A builds the real engine. Existing contract v0.2 is a generic "items with a trend" bundle: it is the starting point for F1, but the endpoints listed above (`/trend/point`, `/trend/region`, `/viability`, `/crops`, `/decisions`) are not in `contracts/api.md` yet. Writing them is lane A's first task on Saturday (task A1 in `TASKS.md`).

**Live point trends.** `/trend/point` fetches NASA POWER live and runs the trend engine on the fly. The API imports the engine from `ml/` as a function (lane A defines its signature in `contracts/api.md`); lane B never edits `ml/`.

## 8. Data

| Data | Use | Status |
|---|---|---|
| NASA POWER monthly grid, **any region of the world**, 0.5 x 0.625 deg, 2001 to 2025, same 6 measurements | F1 trend maps everywhere | **Live fetch per region, cached on disk** (`region_monthly()`), verified Fri. World temperature yearly means are in git. Optional bulk download of everything: `python run.py world` (about 4 hours, not required) |
| NASA POWER monthly grid, Egypt, 0.5 deg, 2001 to 2025: T2M, T2M_MAX, PRECTOTCORR, GWETTOP, GWETROOT, RH2M | F2, F3, F4 for Egypt; method tests (D1) | Downloaded and working (`python run.py power`) |
| NASA POWER monthly point API, any location (add T2M_MIN) | F1 point and city | Verified live |
| FAO ECOCROP crop requirements (optimal and absolute temperature and rainfall ranges) | F3 | Source verified (FAO data sheets; also packaged for 1,710 plants). Lane C builds `data/crops/crops.csv` for the chosen crops |
| NASA GISTEMP global means | F5 validation | Verified public CSV |
| MODIS vegetation / land temperature (AppEEARS) | Optional evidence layer (P2) | Script ready; only if time |
| Official challenge Resources tab | Prefer listed datasets | Lane C pastes it into `docs/DATA.md` |

## 9. Decisions to make during the hackathon (not fixed here on purpose)

Each decision has an owner and a deadline. Record the outcome in `docs/DECISIONS.md` with one line of reasoning.

| # | Decision | Owner | Deadline (Cairo) |
|---|---|---|---|
| D1 | Trend and confidence method (compare candidates on our data, pick the most reliable), including the analysis period: POWER covers 2001 to 2025, older notes used 2003 to 2025 (MODIS era) | A | Sat 12:00 |
| D2 | Confidence level thresholds and wording | A + C | Sat 12:00 |
| D3 | Globe library and map library | B | Sat 10:00 |
| D4 | Farming viability score definition (which measurements, how combined) | A + C | Sat 15:00 |
| D5 | Projection method for +5 / +10 years and how uncertainty is shown | A | Sat 18:00 |
| D6 | Final crop list (8 to 12) and how irrigation is modeled | C | Sat 14:00 |
| D7 | Extra countries beyond Egypt for the **farming** features F2 to F4 (trends already cover the world) | all | Sun 08:00 |
| D8 | Final product name | all | Sat 20:00 |
| D9 | Where the app is hosted for judges (needs a Python backend for live point trends; fallback: recorded demo running from cache) | B | Sat 18:00 |

## 10. Team, lanes and tasks

Lanes are **work areas** (folders + a branch), not people. The team decides who takes what; a person claims a task by writing their name next to it in `TASKS.md`.

| Lane | Branch | Owns (may edit) | Who |
|---|---|---|---|
| A: analysis + integration | `lane/a-ml` | `ml/`, `contracts/`, `CLAUDE.md`, `PROJECT_PLAN.md`, `docs/DECISIONS.md`, `docs/METHODS.md`; merges to `main` | Mohammed, Claude account 1 |
| B: API + app | `lane/b-app` | `api/`, `app/` | Mohammed, Claude account 2 |
| C: data + science + story | `lane/c-data` | `data/`, `docs/DATA.md`, `docs/RESEARCH.md`, `docs/PITCH.md`, `docs/REFERENCES.md`, `demo/` | teammates (split among themselves) |

**More than one person in a lane?** Each person works on their own branch cut from the lane branch, named `lane/c-<task>` (for example `lane/c-crops`), touches only the files of the task they claimed, and opens a pull request into `main` like everyone else.

Rules: stay in your lane, contracts first, push every 30 to 60 minutes, `/handoff` before stopping, lane A merges green pull requests only. Full rules in `CLAUDE.md`.

### Tasks
The full task list, with which tasks run **in parallel** and which **wait for another task**, lives in **`TASKS.md`**. Tick tasks there, never here.

### Timeline (merge points)

| When (Cairo) | Phase | Merge point: must work on `main` |
|---|---|---|
| Fri (now) | 0: prepare, no product code | repo, lanes, data on every laptop (done) |
| Sat 09:00 to 13:00 | 1: F0 + F1 skeleton | **13:00:** F1 on real data: trend map for Egypt and one other country by live fetch, and one live point |
| Sat 13:00 to 20:00 | 2: F2 + F3 core | **20:00:** F0 to F3 on real data, first deploy (D9) |
| Sat 20:00 to Sun 02:00 | 3: F4 + F5 | **02:00:** decisions tab and Methods page with real numbers |
| Sun 02:00 to 08:00 | night | sleep in shifts; only long running jobs |
| Sun 08:00 to 14:00 | 4: polish + F6 tour | **14:00: FEATURE FREEZE** |
| Sun 14:00 to 23:59 | 5: story + submission | **submit by 20:00**, repo public, improve until 23:59 |

## 11. Definition of done for the submission
- R1 to R7 each shown on screen in the demo.
- F0, F1, F5 complete (P0). F2, F3, F4, F6 as complete as time allows, each clearly labeled.
- Every number on screen traceable to NASA data and our code; every future view labeled "if current trends continue".
- Public repo, working deployed link or recorded demo, video with English subtitles, references complete.

## 12. Risks and how we handle them

| Risk | Handling |
|---|---|
| Climate data alone says all of Egypt is unviable (desert, little rain) | Irrigation toggle; viability for irrigated land focuses on heat and water stress, not rainfall |
| Projections taken as forecasts | Always labeled "if current trends continue", show uncertainty, short horizons only (max 10 years) |
| "Farmers should migrate" sounds harmful or overconfident | Frame as planning signals for support and adaptation; show evidence and confidence |
| 0.5 deg grid (about 55 km) too coarse for buying land | Say so in limitations; position as regional screening, the first step before field studies |
| Globe library eats too much time | Fallback: 2D map with the same tabs (decide by Sat 12:00 if the globe is not working) |
| Live point API slow or down during demo | Cache points used in the tour; demo runs from cache |
| Live fetch of a new region is slow (5 to 40 s) or NASA is down during the demo | Every region and point used in the demo is fetched beforehand and served from the local cache; loading message for new regions; Egypt grid is in the repo as fallback |
| Trend engine too slow for a big region | Engine works on whole arrays at once, not a loop over cells (task A4) |
| Too many features | P0 first; P1 in order F2, F3, F4, F6; cut P2 freely |
