---
license: cc-by-4.0
library_name: xgboost
tags:
  - agriculture
  - climate
  - crop-suitability
  - nasa
  - nasa-power
  - tabular-classification
  - space-apps-2026
pipeline_tag: tabular-classification
---

# CropShift Earth crop suitability model (v3.1)

NASA Space Apps Challenge 2026, Cairo, challenge "Be An Earth System Trend Detective!".
Used by the CropShift Earth app to show which of 40 crops fit a place today, in 2030 and in 2035 if current climate trends continue.

## What it does
For any place on land, it scores each of **40 crops** from 0 to 1: how typical the local climate is of the places where that crop is grown today. 0.5 means the climate is as typical of places that grow the crop as of places that do not. It is **not** a yield and not the chance of a good harvest. Two modes: **irrigated** (water supplied) and **rain only**; an irrigation share between 0 and 1 is also accepted.

## Inputs
10 climate features from six NASA POWER measurements (T2M, T2M_MAX, PRECTOTCORR, RH2M, GWETTOP, GWETROOT), as yearly values or 2001 to 2025 averages:
`t_mean`, `t_coldest`, `t_warmest`, `tmax_hottest` (°C), `rain_annual` (mm/year), `rain_wettest3_share` (0 to 1), `rh_mean` (%), `soil_top_wetness`, `soil_root_wetness`, `soil_root_wetness_min` (0 to 1).

## Training
- **Labels:** where crops are grown today, from IFPRI MapSPAM 2020 v2r2 harvested area, summed onto the NASA POWER grid (0.5 x 0.625 degrees): 22,450 farmland cells on every continent. A crop counts as grown where it covers at least 2% of the cell's harvested area or at least 500 ha.
- **Algorithm:** one XGBoost classifier per crop (200 trees, depth 6), class-balanced, chosen from 8 algorithm families by spatial block cross-validation (10 x 10 degree blocks). Unfarmed deserts and fully irrigated farmland are added as rain-only counter-examples, and a documented rain gate stops rain-only scores below 100 mm a year.
- **Packed for speed:** the 8,000 trees are packed into `crop_suitability_v3.npz` and evaluated with numpy only (matches XGBoost to 3e-7). No XGBoost needed to run it.

## How good is it (held-out regions, mean over 40 crops)
| Check | Result |
|---|---|
| AUC, all farmland / irrigated / rain-fed | 0.899 / 0.847 / 0.880 |
| Worst crop AUC | 0.821 |
| TSS / Brier / calibration error (ECE) | 0.637 / 0.129 / 0.040 |
| Trained without Egypt: recognizes Egypt's real crop list (FAOSTAT), AUC | 0.930 |
| Rain only, crops rated suitable on unfarmed deserts (< 100 mm) | 0 |

Full numbers: `metrics_v3.json`; full card with every design choice and limitation: `MODEL_CARD_FULL.md`.

## Use it
```python
import crop_engine_v3 as ce                      # needs numpy only
eng = ce.CropSuitabilityEngine.load("crop_suitability_v3.npz")

features = dict(t_mean=22.0, t_coldest=14.0, t_warmest=28.5, tmax_hottest=35.5, rain_annual=25.0,
                rain_wettest3_share=0.6, rh_mean=52.0, soil_top_wetness=0.1,
                soil_root_wetness=0.12, soil_root_wetness_min=0.1)
print(eng.rank(features, mode="irrigated")[:5])   # e.g. onion, vegetables, tomato, citrus ...

report = ce.point_report(eng, lat=30.04, lon=31.24)   # live NASA POWER data for any point (internet needed)
```

## Limitations
- About 55 km cells: regional screening, not advice for a single farm.
- It learns where crops are grown today, which also reflects markets, policy, diet and water, not only climate.
- Irrigated mode assumes water can be supplied; it does not show that water exists.
- Olive and date palm are not separate crops in MapSPAM and are not covered.
- Future scores in the app continue today's trends; they are not climate forecasts.

## Credits and licence
- Climate: NASA POWER (MERRA-2), https://power.larc.nasa.gov
- Crop maps: International Food Policy Research Institute (IFPRI), 2026, SPAM 2020 v2r2, Harvard Dataverse, https://doi.org/10.7910/DVN/SWPENT , CC BY 4.0. *This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no responsibility for the analyses or interpretations of the data presented here.*
- Egypt crop list check: FAOSTAT.
- v2 training code written with Manus (AI agent) on Kaggle; v3 retraining and packing with Claude (Anthropic). Reviewed and tested by the team.
- Licence: CC BY 4.0 (same as the training labels).
