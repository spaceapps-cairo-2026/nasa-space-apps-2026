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
- [x] **A5** D4: farming viability score per cell per year, its trend and confidence | needs: A4 | owner: Mohammed (model trained with Manus) + Claude (connected it: `ml/crop_model/`, `ml/crop_outlook.py`, `python run.py crop-model`)
- [x] **A6** Crop suitability per cell per year, rain-fed and irrigated | needs: C3, A2 | owner: Mohammed (model trained with Manus) + Claude (connected it: `ml/crop_model/`, `ml/crop_outlook.py`, `python run.py crop-model`)
- [x] **A7** D5: projections for +5 and +10 years with uncertainty, labeled "if current trends continue" | needs: A5, A6 | owner: Mohammed (model trained with Manus) + Claude (connected it: `ml/crop_model/`, `ml/crop_outlook.py`, `python run.py crop-model`)
- [x] **A8** Decision rankings for investors and planners (every row links to its evidence) | needs: A7 | owner: Mohammed (model trained with Manus) + Claude (connected it: `ml/crop_model/`, `ml/crop_outlook.py`, `python run.py crop-model`)
- [x] **A12** Accuracy pass: trends checked against NASA GISTEMP stations and GPCP rain (`python run.py nasa-check`), crop projections with the 2015 rain record step removed from the moisture trends, model fine-tuning sweep (v3.1 kept), contract v0.7 `station_check`, app hiccups fixed | owner: Claude for Mada
- [x] **A11** Crop model v3.1 (labels: >= 500 ha counts as grown) + contract v0.6 (temperature anywhere with no download) | owner: Claude for Mohammed
- [x] **A10** Crop model v3: retrained locally to remove rain-only false alarms (same XGBoost as Manus; crop-aware counter-examples + rain gate; about 170 variants on one fixed held-out suite) | owner: Claude for Mohammed | `ml/crop_model/retrain/`, `python ml/crop_model/retrain/train_v3.py`
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
- [ ] **C4** `docs/REFERENCES.md`: every dataset, library and AI tool, kept current all weekend | needs: none | owner: ___ (completed Sat 14 Nov by Claude for Mada; keep adding video and slide images)
- [ ] **C5** Validation (F5): reproduce the GISTEMP rate with our engine, check one known real change, write the limitations | needs: A4, C2 | owner: ___
- [x] **C6** Pitch draft in `docs/PITCH.md` with real numbers | needs: A4 | owner: Claude for Mada (also `docs/SUBMISSION.md`, the submission page text)
- [ ] **C7** Demo script: the tour story step by step and the list of points to cache for it | needs: B6, B7, B8 roughly working | owner: ___
- [ ] **C8** Demo video with English subtitles, and slides | needs: feature freeze (Sun 14:00) | owner: ___
- [x] **C9** (done by lane A for Mada, Sat 14 Nov: Saudi Arabia, `python run.py crop-model SAU`; the team still confirms D7) D7: prepare 1 or 2 more focus countries for the farming features (data is already in the world grid; needs irrigation and crop notes per country) | needs: none | owner: ___
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
- FYI (from A, Sat 14 Nov, MENA, asked by Mada): 20 farming countries; PULL BEFORE YOU EDIT `app/data/countries.geojson`, `app/data/borders_50m.geojson`, `app/data/places.json` (one Palestine, the Golan in Syria, no "Israel": `node scripts/palestine_borders.js`; please keep it when you update map data), `app/js/geo.js` (`describePlace`: a town within 15 km names its country when the outline misses it), `app/index.html` (welcome line), `api/main.py` (country list from `ml/focus_countries.py`, `/api/farming/countries` sorted by name, `_load` cache 32).
- FYI (from A, Sat 14 Nov, Saudi Arabia, asked by Mada): PULL BEFORE YOU EDIT `app/index.html` (country picker `#farm-country` in the farming tabs), `app/js/main.js` (`state.farm.iso`, `setFarmCountry`, `showFarmCountry`, `loadFarmCountries`, `farmPlace` per country), `app/js/api.js` (`farmingCountries`), `app/js/farming.js` (country name in a caution), `api/main.py` (`FARMING_COUNTRIES` has SAU, new `/api/farming/countries`).
- FYI (from A, Sat 14 Nov, accuracy pass, asked by Mada to fix the whole app in lane A's session): PULL BEFORE YOU EDIT `app/js/trends.js` (`stationHTML`: weather station line for air temperature, contract v0.7 `station_check`), `app/js/farming.js` (station line and caution in the place panel, Decisions badges from `station_evidence`, coordinates for unnamed places, "(no farmland today)" tag), `app/js/methods.js` (Check 5 = NASA records, Giovanni is Check 6), `app/js/main.js` (`farmPlace`: border cells never named after the neighbour, e.g. Taba was "Jordan"), `app/js/globe.js` (`when()`: waits while the style loads instead of giving up after 15 s, which lost the Whole Earth layer), `app/js/tour.js` (two captions), `api/main.py` (API 0.7, `Cache-Control: no-cache` on app files so browsers stop running old JavaScript after an update, plain sentence for 422 errors).
- FYI (from A, Sat 14 Nov, layout): PULL BEFORE YOU EDIT `app/style.css`, `app/js/trends.js` (drawChart: height and ResizeObserver), `app/js/globe.js` (credits start folded), `app/js/geo.js` (fast border cutting). Breakpoint is now 800 px.
- FYI (from A, Sat 14 Nov, contract v0.6): `data_from` may now be `world` (air temperature outside Egypt is read from the committed world grid, no download). The Data line in the trend panel prints it as is; consider a friendlier label for all four values (repo, world, cache, nasa). Tiny countries (Luxembourg) now get a map instead of a 400.
- FYI (from A, Sat 14 Nov, v3): crop model v3 replaced v2 (rain-only false alarms removed). Asked to finish the whole app in lane A's session, so these were edited in `app/`. PULL BEFORE YOU EDIT: `app/js/farming.js` (legend: score 0 is "a climate unlike the places that grow it", not "cannot grow"; "stable" removed from the change legend; rain-only callout no longer mentions the Nile and wells), `app/js/tour.js` + `app/js/main.js` (`setCrop` takes a list of preferred crops; the tour's food step shows temperate fruit with the model file). Optional cleanup: `/api/meta` and `/api/predictions` still serve the Friday skeleton ("FAKE DATA") even with MOCK=0; the app does not call them.
- FYI (from A, Sat 14 Nov): the trained crop model now writes `ml/outputs/farming_EGY.json` (40 crops, no heat limit, no apple, no date palm or olive). Mohammed asked for it to be finished in lane A's session, so 3 small edits were made in `app/`, PULL BEFORE YOU EDIT: `app/js/farming.js` (place panel: "Farmed today" line and two cautions from the new optional fields `farmland` and `outside_training`), `app/js/methods.js` (data line names IFPRI MapSPAM and FAOSTAT and carries the IFPRI notice, which the licence asks for), `app/index.html` (welcome line no longer promises the heat limit). The tour's crop steps fall back to the first crop (wheat) with the general captions; pick a better story crop if you like (cotton and temperate fruit show a north / south contrast).
- FYI (from A, Fri 23:55): Mohammed asked for the six lane B requests of Fri 23:35 to be fixed in lane A's session, so `app/` was edited there. PULL BEFORE YOU EDIT these files: `app/js/main.js`, `trends.js`, `farming.js`, `tour.js`, `api.js`, `app/index.html`, `app/style.css`, `docs/CONNECT_FARMING_MODEL.md`. What changed: (1) the trend map sends `country=<ISO>`, so counts, FDR and the average are for the country (Egypt now 84 proven warming, not 104); (2) the `region` / `world` flags of `/api/variables` switch the map button and the whole Earth checkbox off with a plain note, and the map comes back when the measurement changes; (3) the trend panel shows "Could this be luck?" as a percentage and a clearer 95% range line; (4) the farming tabs adapt to the outlook file: crop list, one button per horizon, missing water mode or heat data switches that control off, no hardcoded FAO text (it comes from the file's `source` and `score_note`); (5) cell size text is computed from the latitude; (6) tour captions use the crop and numbers that exist. Please review.
- FYI (from A, Fri 23:35): 3 lines changed in `api/main.py` (lane A wrote the trend endpoints in B4): `/api/trend/region` passes the optional `country` to `live.region_trend`, and `API_VERSION` is `"0.4"`. Please keep them when you merge.
- FYI (from A, Fri 23:35): first load of a country is a live NASA download (about 15 s for Egypt per measurement) and anything over 12 uncached blocks is refused (413), for every measurement including air temperature. Mohammed's laptop has the whole world cached for T2M only, so big countries work there and may fail on another laptop. Run `python demo/warm_cache.py` on the demo laptop.

## Lane C inbox
- DONE (Sat 14 Nov, asked by Mada). REQUEST (from A, Sat 14 Nov): add to `docs/REFERENCES.md`: Hugging Face Spaces (free Docker hosting, https://huggingface.co/spaces) hosts the public demo; Docker base image python:3.12-slim; optional huggingface_hub (deploy script only).
- REQUEST (from A, Sat 14 Nov): `data/README.md`: farming outlooks now exist for 20 Middle East and North Africa countries (`ml/outputs/farming_<ISO>.json`, list in `ml/focus_countries.py`). Pitch: the app names Palestine only and puts the Golan in Syria (decision in `docs/DECISIONS.md`).
- REQUEST (from A, Sat 14 Nov): `data/README.md`: add `ml/outputs/farming_SAU.json` (Saudi Arabia farming outlook, built from NASA POWER tiles downloaded by `python run.py crop-model SAU` into `data/cache/`, gitignored). For the pitch: Saudi greening is irrigation (groundwater), our maps show climate fit and warming, not the greening itself.
- DONE (Sat 14 Nov, asked by Mada). REQUEST (from A, Sat 14 Nov): add to `docs/REFERENCES.md`: NASA GISTEMP v4 250 km gridded anomalies (GISTEMP Team, 2026, NASA Goddard Institute for Space Studies, https://data.giss.nasa.gov/gistemp/; Lenssen et al. 2019, JGR Atmospheres 124, 6307 to 6326), used by `ml/nasa_check.py` and the app's weather station line; GPCP v2.3 monthly precipitation (Adler et al. 2018, Atmosphere 9, 138; data from NOAA PSL, https://psl.noaa.gov/data/gridded/data.gpcp.html), used to check the POWER rain jump; xarray and netCDF4 (reading them, check script only).
- REQUEST (from A, Sat 14 Nov, v3 addendum to the next line): the crop model in the app is now v3, retrained locally with XGBoost 3.4 and scikit-learn 1.9 (training only) by Claude; held-out AUC 0.90 still holds for the pitch.
- REQUEST (from A, Sat 14 Nov): add to `docs/REFERENCES.md` (the crop model now in the app): IFPRI, 2026, Global Spatially-Disaggregated Crop Production Statistics Data for 2020 Version 2.0 Release 2 (SPAM 2020 v2r2), Harvard Dataverse, https://doi.org/10.7910/DVN/SWPENT, CC BY 4.0, with the sentence the licence asks for: "This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no responsibility for the analyses or interpretations of the data presented here."; Yu et al. 2020, Earth System Science Data 12, 3545 to 3572 (SPAM method); NASA POWER archive on AWS (global training features); FAOSTAT Egypt area harvested 2015 to 2024 via Kaggle `sayedkhaled2000/egypt-crop-yield-processed-pivot-table` (model check); our Kaggle dataset `mohossameldeen/nasa-2026-earth-trends-dataset`; libraries used in training only: XGBoost, LightGBM, scikit-learn; AI tools: Manus (trained and evaluated the crop model, wrote its notebook), Claude (connected it). Also a row in `data/README.md` for `ml/crop_model/training/cropshift_v2_training_cells.parquet`, and in the pitch: 40 crops, AUC 0.90 on held-out regions, never "yield" or "forecast".
- REQUEST (from A, Sat): in demo/warm_cache.py set TOUR_COUNTRIES to ["EGY", "SDN"]: the tour's opposite trends step now uses Sudan (192 cells cooling, 25 warming), not Kenya. Also please do not use rain in the demo or pitch: the POWER rain record jumps around 2015 (docs/METHODS.md section 9).
- FYI (from B, Sat 00:10): C5 validation numbers are drafted in ml/validate.py (GISTEMP cross-check, false alarms, FDR effect, farming sanity checks) and shown in the app's 'How we know' panel; please review the wording and add the known real-world change check.
- REQUEST (from B, Fri 22:20): add to docs/REFERENCES.md: Natural Earth 1:50m admin 0 countries (app/data/borders_50m.geojson, cuts every country's trend map to its border).
- REQUEST (from B, Fri 20:15): add to docs/REFERENCES.md: Natural Earth 1:110m countries and 1:50m populated places (public domain, naturalearthdata.com), used for borders and search in app/data/.
- REQUEST (from B, Fri 21:05): also add: Natural Earth 1:10m admin 0 (detailed Egypt border, app/data/regions/EGY.geojson); polygon-clipping 0.15.7 (MIT, cuts map cells to the border); Sentinel-2 cloudless 2020 by EOX (close-up imagery, CC BY-NC-SA 4.0, contains modified Copernicus Sentinel data 2020); NASA GIBS VIIRS SNPP true color 2025-07-20 (fallback close-up imagery).
- REQUEST: add to `docs/REFERENCES.md`: SciPy and NumPy (trend engine), pymannkendall and statsmodels (used only to cross-check our engine in tests), NASA POWER monthly point API (`data/power_point_fetch.py`), and the method papers: Sen 1968 (slope), Mann 1945 / Kendall 1975 (test), Benjamini and Hochberg 1995 (FDR), Pettitt 1979 (change point), Bayley and Hammersley 1946 / Yue and Wang 2004 (effective sample size). Claude (Anthropic) wrote the engine code.
