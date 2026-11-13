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

- [x] **A1** Contracts for F1: point trend and region trend map (compact grid, not one JSON object per cell; see `PROJECT_PLAN.md` section 6), fixtures, endpoints in `contracts/api.md`, and the Python signature of the trend function the API calls | needs: none | owner: Mohammed (Claude)
- [x] **A2** Contracts + fixtures for F2 viability, F3 crops (both modes, irrigated and rain-fed), F4 decisions, so lane B can build every tab on fake data | needs: A1 | owner: Eyad + Claude wrote `contracts/farming.schema.json` and the fixture; Mohammed (Claude) reviewed and tightened it (v0.4) and added `python run.py farming-check`
- [x] **A3** D1 + D2: compare trend and confidence methods on the Egypt grid, pick one, set confidence levels and wording (with C), write it in `docs/DECISIONS.md` | needs: none | owner: Mohammed (Claude)
- [x] **A4** Trend engine: a function that takes the arrays from `region_monthly()` (any region, live fetched) and returns the trend map; works on whole arrays, not a slow loop over cells. Plus the point function for live requests, and the world temperature overview from `data/processed/world/T2M_annual.npz` | needs: A1, A3 | owner: Mohammed (Claude)
- [ ] **A5** D4: farming viability score per cell per year, its trend and confidence | needs: A4 | owner: ___
- [ ] **A6** Crop suitability per cell per year, rain-fed and irrigated | needs: C3, A2 | owner: ___
- [ ] **A7** D5: projections for +5 and +10 years with uncertainty, labeled "if current trends continue" | needs: A5, A6 | owner: ___
- [ ] **A8** Decision rankings for investors and planners (every row links to its evidence) | needs: A7 | owner: ___
- [ ] **A9** Merge points: merge green PRs at each merge time; Sun 10:00 freeze all numbers; final tests green | needs: none | owner: ___

## Lane B: API + app (`api/`, `app/`)

- [x] **B1** D3: choose globe and map libraries, bundle them into `app/vendor/` (must work offline except map tiles) | needs: none | owner: Eyad + Claude
- [x] **B2** F0: globe, country/city search, click a point, fly to the area, outline it, pass the selection to every tab | needs: B1 | owner: Eyad + Claude
- [x] **B3** F1 Trends tab on fixtures: measurement picker, time series chart with trend line, rate per decade, confidence label, trend map for any selected country and the whole globe with "not proven" in grey, plain sentence | needs: A1 | owner: Eyad + Claude
- [x] **B4** API: `/trend/point` and `/trend/region` on fixtures (`MOCK=1`), then real data; `/trend/region` works for any country: calls `region_monthly()` (live fetch, cached) then the engine, with a loading state in the app; farming endpoints answer "farming analysis available for: Egypt" outside focus countries | needs: A1 (real: A4, C1) | owner: Mohammed (Claude). Done: the 4 trend endpoints, mock and real. UI loading state and farming endpoint added by Eyad + Claude
- [x] **B5** Methods page layout (F5); text and validation numbers come later from A and C | needs: none | owner: Eyad + Claude
- [x] **B6** Farmland tab (F2): gaining / losing / stable map, horizon selector (now, +5, +10), "crossing" highlight, projection label | needs: A2 | owner: Eyad + Claude
- [x] **B7** Crops tab (F3): mode A crop to places, mode B place to crops, irrigation toggle | needs: A2 | owner: Eyad + Claude
- [x] **B8** Decisions tab (F4): investor and planner lists, each row opens the map and evidence | needs: A2 | owner: Eyad + Claude
- [ ] **B9** D9: hosting; first deploy by Sat 20:00 | needs: B2, B3, B4 | owner: ___
- [x] **B10** Guided tour (F6): one button plays the story end to end, from cached data | needs: B2 to B8, C7 | owner: Eyad + Claude

## Lane C: data + science + story (`data/`, story docs, `demo/`)

- [x] **C1** POWER point fetch for any lat/lon (`T2M_MIN` added) with a local cache in `data/cache/` | needs: none | owner: Mohammed (Claude)
- [x] **C2** GISTEMP global means: download script and tidy table for validation (`data/processed/gistemp_global_annual.csv`) | needs: none | owner: Mohammed (Claude)
- [ ] **C3** D6: pick the final 8 to 12 crops from the 20 already in `data/crops/crops.csv` (FAO ECOCROP, built Fri), decide how irrigation is modeled | needs: none | owner: ___
- [ ] **C4** `docs/REFERENCES.md`: every dataset, library and AI tool, kept current all weekend | needs: none | owner: ___
- [ ] **C5** Validation (F5): reproduce the GISTEMP rate with our engine, check one known real change, write the limitations | needs: A4, C2 | owner: ___
- [ ] **C6** Pitch draft in `docs/PITCH.md` with real numbers | needs: A4 | owner: ___
- [ ] **C7** Demo script: the tour story step by step and the list of points to cache for it | needs: B6, B7, B8 roughly working | owner: ___
- [ ] **C8** Demo video with English subtitles, and slides | needs: feature freeze (Sun 14:00) | owner: ___
- [ ] **C9** (P2, only if time) D7: prepare 1 or 2 more focus countries for the farming features (data is already in the world grid; needs irrigation and crop notes per country) | needs: none | owner: ___
- [x] **C11** Live region fetch: `region_monthly()` in `data/power_world_fetch.py` (any box on Earth, cached on disk); world temperature yearly means in `data/processed/world/` | owner: Mohammed (Claude)
- [x] **C12** Before the demo: fetch once every region and point the tour uses, so the demo runs from the local cache | needs: C7 | owner: Eyad + Claude (python demo/warm_cache.py)
- [ ] **C13** (optional, not required) Bulk world download `python run.py world` (about 4 hours, resumable): makes every region instant and enables the globe overview for all 6 measurements | needs: none | owner: Mohammed
- [ ] **C10** (P2, only if time) MODIS evidence layer via AppEEARS | needs: none | owner: ___

## Everyone, Sunday

- [ ] Submission page text, references complete (data, libraries, AI tools used)
- [ ] Make the repo public; **submit by 20:00**; improve until 23:59

## Lane A inbox
- FYI (from B, Sat 01:45): to connect the trained crops / farmland model to the Crops, Farmland and Decisions tabs, make it write ml/outputs/farming_EGY.json in the format of contracts/farming.schema.json; see docs/CONNECT_FARMING_MODEL.md. No UI change needed. ml/farming.py (FAO calculator) is only the stand-in.
- FYI (from B, Fri 23:40): A5 to A8 for Egypt are drafted in ml/farming.py (FAO ECOCROP per cell, irrigated and rain-fed, now / 2030 / 2035 by each cell's own trend with its 95% range, years to heat limit) and served by /api/farming. Please review the method; change anything you disagree with.
- DONE (A, Fri 23:35): masking to the border before FDR is in `live.region_trend(..., country="EGY")` and `/api/trend/region?country=EGY` (contract v0.4, any country). Original request follows. REQUEST (from B, Fri 20:15): the Egypt region grid is the full 22 to 32 N, 25 to 35 E box, so it includes sea, Libya, Sudan and Saudi cells. Consider masking to Egypt's border (app/data/countries.geojson has it) before FDR. Also /api/trend/cell needs cell_trend() for the cell chart; the app falls back to the map numbers until then.
- REQUEST (from B, Fri 18:55): record D3 in docs/DECISIONS.md: MapLibre GL JS 5.6.0 globe projection, NASA GIBS Blue Marble base imagery. Compared against CesiumJS with prototypes; note MapLibre cannot pick fill-extrusion in globe mode, so the app clicks an invisible flat fill layer. Library is vendored in app/vendor.

## Lane B inbox
- REQUEST (from A, Fri 23:35): send the country with the trend map. In `app/js/api.js` `region()` add `country: iso` when a country is selected (contract v0.4, `contracts/api.md` "Country maps"). Today the levels, the correction for many places and the "averaged over this region" sentence use the whole rectangle (sea and neighbours included). With `country=EGY` Egypt has 316 cells and 76 proven warming, not the 104 the app shows now, so the tour caption number will change. Cells outside the country come back as `level` -1.
- REQUEST (from A, Fri 23:35): use the `region` and `world` flags of `/api/variables`. With "Color the whole Earth" ticked, 6 of the 7 measurements show an error under the checkbox (only T2M has a world grid). Daily minimum temperature has no trend map: the button shows an error, the map switches off and stays off when another measurement is picked. Please disable or hide the control when the flag is false, and show the map again after a measurement change. The error texts are plain sentences now, so they can be shown as they are meanwhile.
- REQUEST (from A, Fri 23:35): make the farming tabs survive a trained model's file. Tried in the browser, each of these crashes a tab: no `years_to_heat_limit` (cell panel, Decisions, heat view), no `temp_now_c` / `rain_now_mm` / `temp_trend_per_decade` (cell panel), no `rainfed` scores ("Rain only" button), no crop with id `wheat` (default crop) or `apple` (tour step 5), fewer than 3 horizons ("2035" button; the three button labels are fixed in `index.html`). Until the app has fallbacks, `contracts/farming.schema.json` v0.4 requires these fields and `python run.py farming-check` reports them. Suggested: default crop = first crop in the file, buttons built from `horizons`, hide a view whose data is missing.
- REQUEST (from A, Fri 23:35): the farming texts say FAO ECOCROP whatever wrote the file: sidebar note in `index.html`, "Source: FAO ECOCROP" in `main.js` `cropInfo()`, "Scores follow FAO ECOCROP" in `farming.js`. With a trained model these would be wrong. Please take the wording from the file's `method`.
- REQUEST (from A, Fri 23:35): `docs/CONNECT_FARMING_MODEL.md`: `years_to_heat_limit` is listed as optional and the climate fields have no note, but the app needs them (see above); `version` is now `"0.4"`; please add the line `python run.py farming-check` under "Check it". Also `tests/test_api_v03.py::test_farming_matches_known_geography` assumes the FAO calculator's answers; decide with the model's owner what replaces it.
- REQUEST (from A, Fri 23:35): "Each cell is about 55 by 60 km" (`main.js`, region note) is only true near Egypt's latitude. A cell is 0.5 x 0.625 degrees: about 55 km tall everywhere, 60 km wide at Egypt, 35 km wide at 60 N.
- FYI (from A, Fri 23:35): 3 lines changed in `api/main.py` (lane A wrote the trend endpoints in B4): `/api/trend/region` passes the optional `country` to `live.region_trend`, and `API_VERSION` is `"0.4"`. Please keep them when you merge.
- FYI (from A, Fri 23:35): first load of a country is a live NASA download (about 15 s for Egypt per measurement) and anything over 12 uncached blocks is refused (413), for every measurement including air temperature. Mohammed's laptop has the whole world cached for T2M only, so big countries work there and may fail on another laptop. Run `python demo/warm_cache.py` on the demo laptop.

## Lane C inbox
- FYI (from B, Sat 00:10): C5 validation numbers are drafted in ml/validate.py (GISTEMP cross-check, false alarms, FDR effect, farming sanity checks) and shown in the app's 'How we know' panel; please review the wording and add the known real-world change check.
- REQUEST (from B, Fri 22:20): add to docs/REFERENCES.md: Natural Earth 1:50m admin 0 countries (app/data/borders_50m.geojson, cuts every country's trend map to its border).
- REQUEST (from B, Fri 20:15): add to docs/REFERENCES.md: Natural Earth 1:110m countries and 1:50m populated places (public domain, naturalearthdata.com), used for borders and search in app/data/.
- REQUEST (from B, Fri 21:05): also add: Natural Earth 1:10m admin 0 (detailed Egypt border, app/data/regions/EGY.geojson); polygon-clipping 0.15.7 (MIT, cuts map cells to the border); Sentinel-2 cloudless 2020 by EOX (close-up imagery, CC BY-NC-SA 4.0, contains modified Copernicus Sentinel data 2020); NASA GIBS VIIRS SNPP true color 2025-07-20 (fallback close-up imagery).
- REQUEST: add to `docs/REFERENCES.md`: SciPy and NumPy (trend engine), pymannkendall and statsmodels (used only to cross-check our engine in tests), NASA POWER monthly point API (`data/power_point_fetch.py`), and the method papers: Sen 1968 (slope), Mann 1945 / Kendall 1975 (test), Benjamini and Hochberg 1995 (FDR), Pettitt 1979 (change point), Bayley and Hammersley 1946 / Yue and Wang 2004 (effective sample size). Claude (Anthropic) wrote the engine code.
