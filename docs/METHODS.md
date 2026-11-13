# Methods notes (REFERENCE ONLY, not decisions)

These are candidate methods and lessons from Friday's data checks. The actual choices are decisions D1 to D5 in `PROJECT_PLAN.md` section 9.
Sections 6 (trend fingerprints) and the MODIS areas belong to an earlier concept and are optional.

Every term is defined in plain words, because judges and users must follow it too.

## 0. What was chosen (decisions D1 and D2, Fri 13 Nov)

Sections 1 to 8 below are the earlier candidate notes. This section is what the engine (`ml/trends.py`) really does.

- **Series:** annual means (a year needs at least 9 valid months), 2001 to 2025. A place needs at least 20 valid years.
- **How much:** Sen's slope per decade, with a 95% range.
- **Is it real:** Mann-Kendall test where the variance is scaled by the lag 1 autocorrelation of the detrended series, $(1 + r_1)/(1 - r_1)$. Short series underestimate $r_1$, so it is first corrected by $(2 + 4 r_1)/n$; only positive $r_1$ is used. We call it "effective sample size" (code name `ess`).
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
| **Effective sample size (chosen)** | **3.3%** | **5.5%** | **6.1%** | **7.5%** |
| Iterative pre-whitening (Wang-Swail) | 3.4% | 5.5% | 6.9% | 8.9% |

Power: share of series with a REAL trend that are found (trend = total change over 25 years in units of the yearly noise).

| Method | rho 0, x1.5 | rho 0.3, x1.5 | rho 0.3, x2.5 | rho 0.5, x2.5 |
|---|---|---|---|---|
| Plain Mann-Kendall | 53.5% | 53.9% | 88.5% | 84.9% |
| Hamed-Rao, all lags | 57.4% | 56.1% | 86.2% | 79.8% |
| Pre-whitening | 30.3% | 15.9% | 29.6% | 20.4% |
| **Effective sample size (chosen)** | **45.3%** | **32.1%** | **64.6%** | **46.1%** |

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
