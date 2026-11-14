# The crop model (crop-suitability-v3)

This folder holds the trained crops and farmland model and everything needed to rebuild it.
v2 was trained with Manus (an AI agent) in a Kaggle style notebook, outside this repo, and brought in on
Sat 14 Nov 2026. v3 (the one the app uses) is v2 retrained here, same algorithm and settings, to remove
rain-only false alarms: see `retrain/README.md`. Lane A owns it.

**In one sentence:** for any place, the model says how well the climate fits each of 40 crops
(0 to 1), with irrigation or on rain only, today and in 5 and 10 years if current trends continue.

Model card (what it is, how good it is, what it gets wrong): `ml/model_card.md`.

## Files

| File | What it is |
|---|---|
| `crop_suitability_v3.npz` | **The model the app uses**: 40 XGBoost classifiers, 8,000 trees, plus the rain-only rain gate in its meta. 5.5 MB |
| `crop_engine_v3.py` | Its runtime (numpy only): the v2 runtime plus the rain gate. Written for v3, do not edit by hand |
| `metrics_v3.json` | v3's held-out numbers next to v2's and the other candidates, runtime fidelity |
| `retrain/` | How v3 was chosen and built: fixed held-out suite, 170+ experiments, `train_v3.py` |
| `crop_suitability_v2.npz` | Manus's v2 model (kept to compare and to roll back): 40 XGBoost classifiers (one per crop), 8,000 trees, packed into plain arrays. 5.5 MB |
| `crop_engine_v2.py` | v2's runtime, written by the training notebook |
| `metrics.json` | Every validation number of v2's training run: the 5 designs, the 8 algorithms, tuning, per crop skill, Egypt checks |
| `training/cropshift_v2_training_cells.parquet` | Training table: 31,333 NASA POWER cells, 10 climate features, MapSPAM 2020 harvested area of 46 crops. 7.4 MB |
| `training/cropshift_v2_crop_suitability.ipynb` | The training notebook (clean, no outputs). About 22 minutes on 6 CPUs, 30 to 35 on Kaggle |
| `training/KAGGLE_DATASET_README.md`, `training/dataset-metadata.json` | Dataset card and metadata for publishing the training table on Kaggle |

## How the app uses it

    python run.py crop-model       runs the model on the Egypt grid, writes ml/outputs/farming_EGY.json (about 3 minutes)
    python run.py farming-check    checks that file before the app reads it
    python run.py api              open http://localhost:8000, tabs Crops, Farmland, Decisions

`ml/crop_outlook.py` is the bridge. It reads the six NASA POWER measurements of the Egypt grid from
`data/processed/power_monthly.parquet`, calls the engine, and writes the file in the shape of
`contracts/farming.schema.json`. The API serves that file at `/api/farming?country=EGY`.
No training library is needed on the demo laptop.

## Use the model directly

```python
import sys; sys.path.insert(0, "ml/crop_model")
import crop_engine_v3 as ce

eng = ce.CropSuitabilityEngine.load("ml/crop_model/crop_suitability_v3.npz")
rep = ce.point_report(eng, lat=30.04, lon=31.24)          # any land point on Earth, live from NASA POWER (about 4 s)
print(ce.summary_text(rep))
rep["modes"]["irrigated"]["ranking"]["now"]               # best crops with irrigation
rep["modes"]["rainfed"]["viability"]["n_suitable_now"]    # crops that fit on rain only
```

`point_report(..., parameter=...)` takes the monthly NASA values you already have and needs no internet.
`eng.suitability(F, mode)` scores rows of the 10 features in `ce.FEATURES` order (rain in mm per year).

## Tests done when v2 was brought in (Sat 14 Nov)

- The model file loads with numpy 2.5 on Python 3.13; no training library is imported.
- Re-scoring the whole Egypt grid from the NASA data in this repo gives the same numbers as the
  training run's own export: 341 land cells x 40 crops x 2 water modes x 3 years, plus the climate
  features and the range of the 2035 scores. Largest difference: 0.
- Cairo (30.0 N, 31.25 E), irrigated: tomato 0.977, onion 0.967, wheat 0.963; 14 of 40 crops fit.
  Rain only: 0 of 40 fit. Same as the training run reported.
- The Kaggle dataset card was checked against the table: 31,333 rows, 157 columns, 46 crops,
  177 countries, 53 S to 70 N, 22,450 farmland cells, 116 of them in Egypt. All correct.

## Tests done when v3 replaced v2 (Sat 14 Nov)

- The numpy runtime reproduces the XGBoost models to 3e-7 on 3,000 world cells and Egypt's farmland, both modes.
- Cairo, irrigated: tomato 0.977, wheat 0.973, onion 0.968; 13 of 40 crops fit. Rain only: 0 of 40.
- Egypt, rain only: no crop scores 50 or more where rain is under 100 mm; above that, only wheat and barley.
- `tests/test_crop_model.py` keeps checking, on every `python run.py check`, that the model loads, that
  Cairo still gives these numbers, that the rain gate touches only rain-only scores, that Egypt has no rain-only
  false alarms, and that the app's file holds the engine's scores.

## Retrain (only if the model must change)

v3: `python ml/crop_model/retrain/train_v3.py` (needs xgboost; steps in `retrain/README.md`). v2 from the notebook:

1. Upload `training/cropshift_v2_training_cells.parquet` to Kaggle as a dataset (the card and metadata are next to it).
2. Import `training/cropshift_v2_crop_suitability.ipynb`, attach that dataset and
   `mohossameldeen/nasa-2026-earth-trends-dataset` (optional: `sayedkhaled2000/egypt-crop-yield-processed-pivot-table` for the FAOSTAT check).
3. CPU, Run All. Do not set `CROPSHIFT_QUICK=1`: the quick mode picks a different, weaker model.
4. Copy `crop_suitability_v2.npz`, `crop_engine_v2.py` and `metrics.json` from the output into this folder,
   then `python run.py crop-model` and `python run.py check`.

Give a changed model a new version name and compare the same numbers in `metrics.json` before it replaces this one.

## Not done, on purpose or for lack of time

- The training table is not published on Kaggle yet (needs the team's Kaggle account).
- No yield, water demand or price model. No soil chemistry. See the limitations in `ml/model_card.md`.
- The model's own confidence labels for crop trends use a plain Mann-Kendall test with no correction
  for year to year memory and no FDR. The app does **not** show them: its evidence badges come from our
  trend engine (decision D1 + FDR). Do not call a crop trend "significant" from the model's labels.
- Rain over Egypt jumps around 2015 in the NASA POWER record, so rain only changes to 2030 and 2035
  rest on a trend that may not be real. The app says so next to the scores.

## Credits

Crop maps: International Food Policy Research Institute (IFPRI), 2026, Global Spatially-Disaggregated
Crop Production Statistics Data for 2020 Version 2.0 Release 2 (SPAM 2020 v2r2), Harvard Dataverse,
https://doi.org/10.7910/DVN/SWPENT, CC BY 4.0.

*This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no
responsibility for the analyses or interpretations of the data presented here.*

Climate: NASA POWER (MERRA-2), https://power.larc.nasa.gov. Egypt crop list check: FAOSTAT.
Training code and analysis written with Manus (AI agent); integration and the v3 retraining with Claude (Anthropic).
