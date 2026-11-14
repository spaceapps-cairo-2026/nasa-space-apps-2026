# Retraining the crop model (v2 to v3)

Why: Manus's v2 model gave rain-only false alarms. In Egypt, 13 dry Red Sea and Sinai cells (under 50 mm of rain)
got sesame, small millets or cowpea at 50 or more on rain alone. 25 northern cells (64 to 217 mm) got 1 to 8 crops
such as citrus, tropical fruit and chickpea.

Cause (diagnose.py): MapSPAM labels some desert farming that really runs on groundwater, spate floods or flood
recession as "rain-fed". Examples are 303 rain-fed-dominant cells under 150 mm in Sudan, Niger, Saudi Arabia, Yemen
and Iraq. So the model learned that rain-fed crops grow in deserts. The v2 counter-examples were too few and too
light to outweigh that, and nothing checked the 100 to 250 mm band.

## How the variants were compared

`harness.py` is the notebook's data prep, labels, spatial folds and metrics, copied exactly. It reproduces the
notebook's published cross-validation numbers. `evalx.py` is the FIXED suite every variant runs through:
- 5 folds of whole 10 x 10 degree blocks
- the notebook's 7 metrics, plus false alarms on held-out dry land (100 to 250 mm, farmed and unfarmed)
- recall of real rain-fed crops at the dry margin (150 to 300 mm), so a fix cannot simply switch rain-fed farming off
- Egypt scored by a model trained without any Egyptian cell

Guardrails, which every variant had to pass: AUC >= 0.8905, TSS >= 0.6282, Brier <= 0.1373, dry-margin wheat and
barley recall >= 0.70, Egypt FAOSTAT AUC >= 0.8647, irrigated fits in Egypt 9.4 to 12.4. Every run is saved in `results/<name>.json`.

| Prefix | Approach | Scripts |
|---|---|---|
| `cx-` | stronger and crop-aware rain-only counter-examples (57 variants) | cx_strategies.py, cx_run.py |
| `lab-` | repair the noisy "rain-fed" desert labels in training rows (41) | lab_strategies.py |
| `fam-` | estimator family and depth: Extra Trees, Random Forest, HistGradientBoosting (40) | fam_strategies.py |
| `gate-` | a documented rain rule applied in rain-only mode, no retraining (34) | gate_strategies.py |
| `combo-`, `xgb-` | the winners combined, with scikit-learn and with XGBoost (Manus's algorithm and settings) | combo_strategies.py, xgb_strategies.py |

## Result (held-out, mean over 40 crops)

| Variant | AUC | Brier | Desert crops/cell | Dry irrigated 100-250 mm | Unfarmed 100-250 mm | Dry-margin recall (cereals) | Egypt FAOSTAT AUC | Egypt rain-only crops/cell (>= 100 mm) |
|---|---|---|---|---|---|---|---|---|
| xgb-v2recipe (= deployed v2) | 0.9045 | 0.1315 | 0.40 | 2.78 | 2.72 | 0.483 (0.764) | 0.917 | 3.73 |
| xgb-cx63 | 0.9020 | 0.1323 | 0.09 | 1.35 | 1.25 | 0.420 (0.782) | 0.933 | 1.73 |
| xgb-gate | 0.8994 | 0.1335 | 0 | 0.94 | 1.14 | 0.415 (0.722) | 0.917 | 0.36 |
| **xgb-cx63-gate (v3)** | **0.8976** | **0.1336** | **0** | **0.52** | **0.67** | 0.378 (0.749) | **0.933** | 0.36 |
| combo-d12-gate (Extra Trees) | 0.8999 | 0.1274 | 0 | 0.73 | 1.19 | 0.421 (0.729) | 0.904 | 0.09 |

v3 keeps Manus's algorithm and tuned settings. It adds the crop-aware counter-examples of `cx-63` and the rain gate
(both described in `train_v3.py`). It has the fewest rain-only false alarms and the best Egypt FAOSTAT agreement.

Cost: held-out AUC falls by 0.007, and the share of real rain-fed crops found at 150 to 300 mm falls from 0.48 to 0.38.
On the very dry margin the model is now cautious rather than generous. The Extra Trees variant is better calibrated
(Brier 0.127), but it has more false alarms and a lower Egypt FAOSTAT AUC.

## Rebuild

    python -m pip install xgboost        # 3.x; only for training, the app needs numpy only
    python ml/crop_model/retrain/train_v3.py      # about 20 s on 20 CPUs: writes crop_suitability_v3.npz + metrics_v3.json
    python run.py crop-model && python run.py check

To rerun one experiment: `python ml/crop_model/retrain/xgb_strategies.py xgb-cx63-gate` (any name in VARIANTS).
Set `N_JOBS` to your number of CPUs.
