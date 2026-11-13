# Log (append only, newest at the bottom)

`HH:MM | lane | what changed`

Fri 02:00 | setup | Skeleton created: contracts v0.1, mock API + app, tests green
Fri 15:43 | A | PROJECT_PLAN.md added; TASKS.md rebuilt as claimable tasks with dependencies; CLAUDE.md, README, /sync updated
Fri 18:26 | A | data/README.md: every dataset, what it represents, which feature uses it, status
Fri 18:38 | C | GISTEMP (gistemp_global_annual.csv, check +0.280 C/decade 2003 to 2025) and FAO ECOCROP crop table (20 crops) added with build scripts
Fri 19:51 | C | data/power_world_fetch.py: world NASA POWER grid (648 tiles x 6 measurements), download started; plan section 6 now: trends worldwide, farming for focus countries
Fri 20:41 | C | World temperature grid complete: data/processed/world/T2M_annual.npz (207,936 cells, 2001 to 2025); other 5 measurements still downloading
Fri 21:54 | C | region_monthly(): live fetch of any region with disk cache (Egypt 0.02 s cached, Japan 42 s first time); plan and tasks switched to live fetch
Fri 20:15 | B | App rebuilt on MapLibre globe: search (177 countries, 1,251 cities), click any point, fly and outline, Trends panel with chart, rate, 95% range, confidence badge, Egypt 3D trend map with legend; v0.3 mock endpoints in api/main.py
Fri 21:05 | B | Map cells clipped to Egypt's detailed border, not proven cells flat; place names on click; sharp close-up imagery (Sentinel-2, auto fallback to NASA VIIRS when blocked)
Fri 22:20 | B | Synced lane B on main (team plan wins: our duplicate crop table dropped). Contract v0.3 DRAFT now follows PROJECT_PLAN section 6: compact grid, /api/trend/region for any box, /api/trend/world, /api/trend/cell by lat/lon. App: trend map for any country cut to its 1:50m border, whole Earth layer when zoomed out. Lane A: please review contracts/api.md
Fri 22:30 | B | demo/blender/: Blender prompt (30 s storyboard), NASA day/night Earth textures (GIBS, 10K), Egypt cells export for Blender; numbers must come from data/summary.json
Fri 23:40 | B | Crops, Farmland and Decisions tabs live for Egypt on ml/farming.py: crop suitability maps, years to heat limit, crops that fit, change by 2035, ranked planning signals with evidence badges; map changes now wait for the map to load (no more errors on early clicks)
