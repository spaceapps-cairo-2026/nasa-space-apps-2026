# Handoff: crop model v3.1, offline temperature, app check (Sat 14 Nov 2026)

Read `CLAUDE.md`, then `PROJECT_PLAN.md`. This note covers the crop model and data work in lane A's checkout (`D:\nasa_space_apps`, branch `lane/a-ml`).

## Where things stand

**The crop model the app uses is v3.1** (`ml/crop_model/crop_suitability_v3.npz`, version id `crop-suitability-v3.1`). It is Manus's v2 retrained here, with the same XGBoost and settings. How it was chosen: `ml/crop_model/retrain/README.md`.

1. **v3: rain-only false alarms removed.**
   - Crop-aware counter-examples up to 250 mm of rain.
   - A documented rain gate: a crop scores 0 below 100 mm a year and reaches full strength at 200 mm (wheat, barley) or 250 mm (other crops). Irrigated scores are never changed.
   - In Egypt, rain only now shows just barley on the north-west coast and in North Sinai.
2. **v3.1: labels fixed.**
   - v3 counted a crop as grown only where it was at least 2% of a cell's harvest. The Nile cells are huge, so crops Egypt grows on tens of thousands of hectares were "not grown". Sweet potato scored 18 where Egypt grows it.
   - v3.1 also counts at least 500 ha as grown. Sweet potato is now 69, beans 69, sesame 70, banana 75, groundnut 68, barley 54.
   - Audit of all 40 crops (`retrain/crop_audit.py`): 1 miss left (soybean, 13,000 ha spread thin) and no false alarms.

Held-out numbers (5 folds of 10 x 10 degree blocks):

| | v2 | v3.1 |
|---|---|---|
| AUC | 0.904 | 0.899 |
| Brier | 0.131 | 0.129 |
| ECE | 0.061 | 0.040 |
| Rain-only false alarms on dry land (crops per place) | 2.7 | 0.6 |
| Egypt FAOSTAT AUC | 0.917 | 0.930 |

**Data fetching (contract v0.6)**
- Outside Egypt, air temperature reads the committed world grid (`data/processed/world/T2M_annual.npz`). Every country answers in under 1 s with no internet, on any laptop. Before this, a laptop without the 131 MB cache refused Russia, Canada, China, Brazil, the USA, Australia, India, Greenland and Antarctica.
- Boxes smaller than a cell (Luxembourg) are widened to one cell.
- Stress test: all 177 countries and 17 edge points answer (194 of 194).
- Other measurements still download from NASA. The biggest countries get the plain "too large to load in one go" sentence for them.

**Checked**
- `python run.py check`: 63 passed, 1 skipped (the Giovanni test needs NASA tiles cached on this laptop).
- A fresh clone and the backend zip pass the same tests.
- Browser: all tabs, the tour and the methods panel, real and mock mode.

## Not done

- Lane C: `docs/REFERENCES.md` citations (IFPRI with its notice, FAOSTAT, Manus, XGBoost, scikit-learn) and a `data/README.md` row for the training table. Required by Space Apps before submitting.
- Lane B (optional): a friendlier label for `data_from`. The unused `/api/meta` and `/api/predictions` still say "FAKE DATA".
- Known limits, documented in the app:
  - The NASA POWER rain record jumps around 2015.
  - Soybean and sunflower score low although Egypt grows a little of them.
  - Rain, humidity and soil maps of the largest countries need the world download (`python run.py world`).

## Rebuild

    python -m pip install xgboost                 # training only; the app needs numpy only
    python ml/crop_model/retrain/train_v3.py      # about 20 s: model (v3.1) + metrics_v3.json
    python run.py crop-model                      # about 3 min: ml/outputs/farming_EGY.json
    python ml/validate.py                         # ml/outputs/validation.json
    python run.py check
