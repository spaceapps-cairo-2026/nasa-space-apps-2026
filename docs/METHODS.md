# Methods spec (lane A builds this from Sat 09:00)

Every term is defined in plain words, because judges and users must follow it too.

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
  - default: `yue_wang_modification_test` (variance correction),
  - also store: `original_test`, `hamed_rao_modification_test`, `seasonal_test`.
  - Our first look found these variants disagree on many Egypt cells. Show that disagreement honestly on the Methods page, and only call a trend significant when the default test passes AND FDR passes.
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
