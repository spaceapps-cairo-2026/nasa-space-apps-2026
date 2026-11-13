# Task board: Egypt Trend Detective

Format: `- [ ] (lane) task`. Tick with `[x]`. Requests to another lane start with `REQUEST:`.
Cairo time. Submission window: Sat 14 Nov 09:00 to Sun 15 Nov 23:59.
Rule: before Sat 09:00 only research, data gathering and setup. Product code starts at 09:00.

## Friday (today): gather data, prepare, then sleep
- [ ] (C) Paste the official Resources tab into `docs/DATA.md` section 0
- [ ] (all) Earthdata account (urs.earthdata.nasa.gov); open appeears.earthdatacloud.nasa.gov once and accept terms
- [ ] (C) `python run.py appeears submit` (MODIS NDVI + land temperature, 5 areas). Processing takes hours: do it NOW
- [ ] (C) `python run.py power` on every laptop (9 seconds, caches all Egypt climate data)
- [ ] (all) Read `docs/CHALLENGE.md` and `docs/METHODS.md`; ask questions tonight, not tomorrow
- [ ] (C) Look at the 5 areas in NASA Worldview (worldview.earthdata.nasa.gov), compare 2003 vs 2025 images, adjust boxes in `data/appeears_request.py` if a box misses the farms
- [ ] (all) `python run.py check` green on every laptop

## Sat 09:00 to 11:00: engine first
- [ ] (A) `ml/trends.py`: annual_means, trend_one (Yue-Wang MK + Sen), add_fdr on POWER data
- [ ] (A) Validation 1: reproduce GISTEMP 2003 to 2025 global slope; table in `ml/model_card.md`
- [ ] (B) App: variable picker + map colored by slope (diverging blue/red), non-significant cells greyed, built on fixtures v0.2
- [ ] (C) `python run.py appeears status`; when done, download and write `data/modis_prepare.py` (netCDF -> monthly long parquet per area, quality masked, LST 8-day -> monthly)

## Sat 11:00 to 14:00: first real map
- [ ] (A) `python run.py trends` writes real POWER trends for T2M, T2M_MAX, GWETTOP, PRECTOTCORR (precip flagged "caution over desert")
- [ ] (B) Click a cell: time series + Sen trend line + change point marker + the plain sentence
- [ ] (A) 13:00 merge to main, everyone `/sync`
- [ ] **14:00 CHECKPOINT:** real POWER map live in the app. If MODIS is not here yet, keep going on POWER.

## Sat 14:00 to 20:00: the opposite trends
- [ ] (A) Same engine on MODIS pixels (NDVI, LST) for the 5 areas
- [ ] (A) Change points (ruptures PELT)
- [ ] (A) `ml/fingerprints.py`: Gaussian mixture on pixel trend vectors, named clusters
- [ ] (B) Area view: zoom to an area, toggle NDVI trend / LST trend / fingerprint map, before vs after slider
- [ ] (C) Validation 3: for each area, Worldview screenshots 2003 vs 2025 next to our fingerprint map; write where we are right and wrong
- [ ] (A) 20:00 integration: merge, check green, real data everywhere, deploy once

## Sat 20:00 to Sun 02:00: prove it
- [ ] (A) Validation 2: synthetic autocorrelated no-trend series, false alarm rate (target near 5%)
- [ ] (A) Methods page data: how many cells are "significant" with plain MK vs corrected MK vs corrected + FDR
- [ ] (B) Methods page in the app (what is Sen slope, p, q, autocorrelation, in plain words)
- [ ] (C) Pitch story draft in `docs/PITCH.md` using real numbers

## Night: Sun 02:00 to 08:00, sleep in shifts

## Sun 08:00 to 14:00: polish the demo path, FEATURE FREEZE 14:00
- [ ] (B) Guided tour: 3 steps (Egypt warms everywhere -> but here it greens and cools -> here it browns and heats)
- [ ] (A) Final numbers frozen in `ml/model_card.md`
- [ ] (B) Final deploy

## Sun 14:00 to 23:59: story and submission
- [ ] (C) Demo video with English subtitles
- [ ] (C) Slides
- [ ] (all) Submission page + References (all datasets, libraries, Claude disclosure)
- [ ] (all) SUBMIT by 20:00, make repo public, then improve until 23:59

## Lane A inbox

## Lane B inbox

## Lane C inbox
