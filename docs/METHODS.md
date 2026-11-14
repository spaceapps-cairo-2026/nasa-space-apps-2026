# Methods notes (REFERENCE ONLY, not decisions)

These are candidate methods and lessons from Friday's data checks. The actual choices are decisions D1 to D5 in `PROJECT_PLAN.md` section 9.
Sections 6 (trend fingerprints) and the MODIS areas belong to an earlier concept and are optional.

Every term is defined in plain words, because judges and users must follow it too.

## 0. What was chosen (decisions D1 and D2, Fri 13 Nov)

Sections 1 to 8 below are the earlier candidate notes. This section is what the engine (`ml/trends.py`) really does.

- **Series:** annual means (a year needs at least 9 valid months), 2001 to 2025. A place needs at least 20 valid years.
- **How much:** Sen's slope per decade, with a 95% range.
- **Is it real:** Mann-Kendall test where the variance is scaled by the lag 1 autocorrelation $r_1$, $(1 + r_1)/(1 - r_1)$. For ranges of 20 years or more, $r_1$ is measured on what is left after a smooth curve (quadratic), corrected by $(3 + 4 r_1)/n$; for shorter ranges on what is left after a straight line, corrected by $(2 + 4 r_1)/n$. Only positive $r_1$ is used. We call it "effective sample size" (code name `ess`; the straight line only version is `ess_line`, the D1 choice until Sat 14 Nov).
- **Many places:** Benjamini-Hochberg q-value over all cells of a map.
- **Levels:** strong evidence (below 0.01), moderate evidence (below 0.05), not proven (the rest). Maps use q, a single place uses p.
- **When:** Pettitt test on the annual series; a start year is shown only for proven trends and only if the test's p is below 0.05.

**Why this method.** `python ml/compare_methods.py` tests 7 methods on 20,000 simulated series of 25 years.

False alarms: share of series with NO trend called significant at p < 0.05 (fair = 5%). rho = how strongly one year resembles the previous one.

| Method | rho 0 | rho 0.2 | rho 0.4 | rho 0.6 |
|---|---|---|---|---|
| Plain Mann-Kendall | 4.5% | 9.5% | 16.6% | 28.2% |
| Hamed-Rao, all lags (pymannkendall default) | 7.9% | 12.8% | 18.9% | 25.2% |
| Hamed-Rao, lags 1 to 3 | 4.4% | 9.2% | 15.0% | 21.5% |
| Pre-whitening | 3.8% | 4.0% | 4.2% | 5.3% |
| Trend-free pre-whitening | 4.5% | 9.9% | 18.9% | 34.3% |
| **Effective sample size, curve (chosen Sat)** | **3.3%** | **5.7%** | **6.8%** | **8.8%** |
| Effective sample size, line (chosen Fri) | 3.3% | 5.5% | 6.1% | 7.5% |
| Iterative pre-whitening (Wang-Swail) | 3.4% | 5.5% | 6.9% | 8.9% |

Power: share of series with a REAL trend that are found (trend = total change over 25 years in units of the yearly noise).

| Method | rho 0, x1.5 | rho 0.3, x1.5 | rho 0.3, x2.5 | rho 0.5, x2.5 |
|---|---|---|---|---|
| Plain Mann-Kendall | 53.5% | 53.9% | 88.5% | 84.9% |
| Hamed-Rao, all lags | 57.4% | 56.1% | 86.2% | 79.8% |
| Pre-whitening | 30.3% | 15.9% | 29.6% | 20.4% |
| **Effective sample size, curve (chosen Sat)** | **45.8%** | **34.1%** | **67.0%** | **50.8%** |
| Effective sample size, line (chosen Fri) | 45.2% | 31.3% | 63.8% | 46.2% |

Reading: the methods that find the most trends do it partly by inventing them. The chosen one is honest in every case and loses less power than pre-whitening. The price: with only 25 years, a real but small trend is often "not proven". That is the honest answer.

On the Egypt grid (357 cells) after FDR: temperature 131 cells proven, topsoil wetness 150, rain 105, humidity 70, root zone wetness 20, max temperature 0. The measured autocorrelation in Egypt is small (median -0.31 to +0.19).

Checks that run in `python run.py check`: our array code equals pymannkendall to 1e-9; false alarms below 8% with and without autocorrelation; GISTEMP 2003 to 2025 gives 0.25 to 0.31 C per decade; FDR equals statsmodels.

Speed: 357 cells in 0.01 s, 5,000 cells in 0.2 s, the whole world (207,936 cells) in about 8 s.

## 1. Prepare each time series
- One series = one place (cell or pixel) + one variable, monthly values.
- Remove the seasonal cycle before trend testing, otherwise summer vs winter swamps everything.
  Two options, implement both, default to (a):
  a. **Annual means**: average the 12 months of each year (needs at least 9 valid months, else that year is missing).
  b. **Seasonal Mann-Kendall**: compare January only with January, February with February, and so on.
- Quality masks: drop MODIS pixels flagged unreliable (pixel_reliability > 1, QC_Day bad) before averaging.
- Analysis window: 2003 to 2025 (23 full years, both MODIS satellites available).

## 2. How much: Sen's slope
- Take every pair of years (i, j), compute the slope between them, $(x_j - x_i)/(j - i)$, and keep the **median** of all those slopes.
- Why: one extreme year cannot drag the median, unlike an ordinary straight-line fit.
- Report per decade: slope x 10, in the variable's real units.

## 3. Significant: Mann-Kendall test, corrected for autocorrelation
- **Mann-Kendall** asks: across all pairs of years, do later values beat earlier values more often than chance would allow? It only uses the order (bigger or smaller), so it does not assume a straight line or a bell curve.
- **Autocorrelation** means one year resembles the previous one (a wet year often follows a wet year). That makes random wiggles look like trends, so plain Mann-Kendall raises false alarms (one public team measured 21% instead of 5%).
- Use `pymannkendall`:
  - default: `hamed_rao_modification_test` (autocorrelation correction),
  - also store: `original_test`, `pre_whitening_modification_test`, `seasonal_test`.
  - DO NOT use `yue_wang_modification_test` from pymannkendall: on the real Cairo series it returned p = 0.0 while every other variant gave p of about 0.02 to 0.025, and a 10,000 run simulation gave 0.016. It collapses on short annual series.
  - Sanity check for any p-value: simulate 10,000 trendless series with the same noise level and count how often their Sen slope is as large as the real one. That fraction must be close to the test's p.
  - Our first look found these variants disagree on many Egypt cells (Yue-Wang was the outlier). Show that disagreement honestly on the Methods page, and only call a trend significant when the default test passes AND FDR passes.
- **p-value**: the chance of seeing a trend at least this strong if there were truly no trend.

## 4. Many places at once: false discovery rate (FDR)
- Testing 357 cells (or 100,000 pixels) at p < 0.05 guarantees many lucky "trends".
- **Benjamini-Hochberg** turns each p into a **q-value**: among all places we call significant with q < 0.05, at most about 5% are expected to be false.
- `statsmodels.stats.multitest.multipletests(p, method="fdr_bh")`. Apply per variable, per map.

## 5. When: change point
- Many Egyptian changes start suddenly (a canal opens, a project starts).
- Use `ruptures` (PELT method, penalty tuned on a few known places) on the annual series to find the year the level or slope changed.
- Report "change around YEAR" only if the segments before and after differ significantly; otherwise "no clear start".

## 6. The AI part: trend fingerprints (opposite trends, same process)
- For each 1 km pixel build a small vector: [NDVI slope, LST slope, NDVI change point year, LST change point year, baseline NDVI].
- Standardize (z-scores) and cluster with a **Gaussian mixture model** (a model that finds groups of similar points, each group shaped like a blurred ellipse; choose the number of groups with BIC, a score that penalizes too many groups).
- Name clusters by their centers, e.g. "new farmland" (NDVI up, LST down), "urban sprawl" (NDVI down, LST up), "stable desert", "stable farmland".
- Show the cluster map: this is the moment in the demo where the "opposite trends" become visible.
- Explain each pixel: which features pushed it into its cluster (distance to cluster centers per feature).

## 7. Validation (Validity criterion)
1. Reproduce GISTEMP global warming rate 2003 to 2025 with our engine. Table: ours vs published.
2. Synthetic test: 1,000 series with autocorrelation and no trend; false alarm rate of our pipeline must be close to 5%. Put the number in the model card.
3. Known places: East Owainat and Toshka must come out as "greening" with a change point consistent with their known development; Greater Cairo edge as "urban sprawl". Check against NASA Worldview images and say where we were wrong.
4. Cross-check: MERRA-2 air temperature trend vs MODIS land surface temperature trend in the same cells. Agreement in desert, disagreement in irrigated areas (expected: irrigation cools the surface more than the air).

## 8. Plain language output per place
Template only from computed numbers, for example:
"Since 2003, plant greenness here rose by 0.05 per decade (strong evidence: q = 0.002). The rise started around 2016. Land surface temperature fell by 0.9 C per decade over the same period. Pattern: new farmland."

## 9. Lessons from our own data (Sat, trend audit)
- **Rain record jump.** NASA POWER `PRECTOTCORR` jumps around 2015 in many places at once: across Egypt the 2016 to 2025 mean is a median 2.9 times the 2001 to 2014 mean, in 80% of grid cells, with Pettitt change years clustered in 2014 to 2016 (Ethiopia roughly doubles; London, Delhi, Phoenix stay flat). Real rain does not triple everywhere in one year, so it looks like a change in how the record is made. Every rain answer now carries a caution (`ml/live.py` `RAIN_CAUTION`). Do not feature rain in the demo until it is checked against an independent rain record.
- **Fill values are not data.** Over the sea POWER soil wetness is exactly 1 every month. A series that never changes is now no data (`ml/trends.py`), not "not proven, 100%".
- **The D1 correction is cautious with step shaped series.** The global mean of our T2M grid is flat until about 2014 and then rises. The effective sample size correction reads that shape as slow swings: p = 0.29 (plain Mann-Kendall: 0.003). This keeps false alarms low (1.0% on Egypt-like noise) at the cost of power. The Methods page says so instead of claiming agreement with GISTEMP.
- **Opposite trends in one country (R7).** Air temperature in Sudan: 192 cells proven cooling in the south (10.5 to 17.5 N, a gradual fall, not a step) and 25 proven warming in the north east. Egypt relative humidity: 73 cells rising in the Western Desert, 20 falling near the Red Sea (change years near 2014, so check against the rain jump before using it).
- **D1 update: memory after a curve (Sat).** The line version read the bend of a flat then rising series as year to year memory and made the test stricter than needed: our whole Earth T2M mean was "not proven" (p = 0.29) while GISTEMP is strong evidence. Measuring memory after a quadratic (with a bias correction of 3 instead of 2, one more number fitted) keeps false alarms close to the line version (25 years: 3.5 / 6.1 / 7.9% at rho 0 / 0.3 / 0.5, line 3.1 / 6.0 / 6.7%), finds more bent changes (flat then rise, rho 0.3: 40% vs 35%) and the same share of straight ones (31% vs 32%). The 95% range still holds the true rate 96.6 / 95.0 / 93.3 / 91.3% of the time at rho 0 / 0.2 / 0.4 / 0.6 (line: 96.6 / 95.3 / 93.9 / 92.8%). Under 20 years a curve leaves too few years to judge memory (rho 0.5, 10 years: 10.8% false alarms), so short ranges keep the line. Result: whole Earth +0.17 C per decade, p = 0.046; without Antarctica p = 0.016; world cells proven warming 29,620 (was 22,724); Egypt unchanged (84 of 323). Evidence: `python ml/compare_methods.py`.
## 10. The crop model (crops, farmland and decisions tabs, Sat 14 Nov)

Full card: `ml/model_card.md`. Files and how to rebuild: `ml/crop_model/README.md`. Bridge to the app: `ml/crop_outlook.py`.

- **What it answers.** For a place and a crop: how typical is this climate of the places where the crop is grown today? 0 to 100, with irrigation or on rain only. 50 = as typical of places that grow it as of places that do not. It is not a yield and not a chance of success.
- **Learned from.** IFPRI MapSPAM 2020 harvested area of 40 crop groups on 22,450 farmland cells worldwide, on the NASA POWER grid. Inputs: 10 yearly climate features from the six NASA POWER measurements (mean, coldest and warmest month temperature, hottest monthly maximum, yearly rain and how seasonal it is, humidity, surface and root zone soil wetness) plus the share of irrigated area.
- **How it was chosen.** 5 designs and 8 algorithm families compared on 5 folds of whole 10 x 10 degree blocks, so neighbours never test each other. Winner: one XGBoost classifier per crop (v2; v3 keeps it, see below).
- **How good.** Held-out AUC 0.90 (irrigated farmland 0.82, rain-fed farmland 0.89), worst crop 0.83 (tomato). Trained without Egypt: 0.85 on Egypt's own crop map, 0.92 on Egypt's FAOSTAT crop list.
- **Deserts.** Without help, rain only mode called deserts suitable, because the only desert farms the model saw were irrigated. Two kinds of counter-examples fixed it (fully irrigated cells copied as "rain only: not grown", and 1,145 unfarmed desert cells): rain only false alarms on held-out deserts fell from 10% to 1%. On our Egypt grid (v3): 0.00 crops fit on rain alone in the 247 cells under 50 mm of rain a year, 10.9 with irrigation.
- **Future years.** Each feature's Theil-Sen trend over 2001 to 2025 is continued to 2030 and 2035 and the model is run again. The 95% range comes from 200 resamples of the years in blocks of 3. This is a projection "if current trends continue", not a forecast.
- **Checked when it came into the repo.** Our re-run on the repo's NASA data equals the training run's own Egypt export on all 77,280 scores (322 cells x 40 crops x 2 water modes x 3 years), to the rounding.
- **v3 retraining (Sat 14 Nov).** v2 still left rain only scores above 50 in 25 cells of the wetter north (64 to 217 mm of rain; citrus at 157 mm is not believable) and in 13 dry Red Sea and Sinai cells. Cause: MapSPAM calls some desert farming on groundwater and floods "rain-fed". About 170 variants were compared on one fixed held-out suite (`ml/crop_model/retrain/`). v3 = same XGBoost + crop-aware counter-examples up to 250 mm + a documented rain gate (0 below 100 mm, full at 200 mm for wheat and barley, 250 mm for others). Held-out AUC 0.904 to 0.898. Rain only false alarms on held-out dry land (100 to 250 mm) fall from 2.7 to 0.5 to 0.7 crops per place. Egypt FAOSTAT AUC 0.917 to 0.933. In Egypt only barley reaches 50 on rain alone, on the north-west coast and in North Sinai. Cost: at 150 to 300 mm about a fifth fewer real rain-fed crops are found.
- **v3.1 labels (Sat 14 Nov).** A share-only label cannot see a crop grown on thousands of hectares inside a giant Nile cell, so v3 scored sweet potato, beans, sesame, banana, groundnut and barley under 50 where Egypt grows them. v3.1 also counts >= 500 ha as grown. Held-out skill is equal or better (Brier 0.129, ECE 0.040), and only soybean (13,000 ha spread thin) is still missed. `ml/crop_model/retrain/crop_audit.py` checks every crop against Egypt's real areas.
- **Lessons.** (1) Irrigated scores assume water: 205 of the 322 Egypt cells have no farmland today, so the app says "no farmland mapped" there. (2) A climate model learns the labels' mistakes: check rain-only answers on held-out dry land, not only on deserts. (3) Check every crop against the country's real statistics, not only the big ones. (3) The rain record jumps around 2015 (section 9), so rain only changes to 2035 rest on a trend that may not be real. (4) 25 cells have a climate outside the training range; the app flags them. (5) The model's own crop trend labels use plain Mann-Kendall and are not shown (rule 10).
