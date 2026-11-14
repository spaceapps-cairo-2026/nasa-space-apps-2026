# Handoff: crop model v3 and app check (Sat 14 Nov 2026)

Read `CLAUDE.md`, then `PROJECT_PLAN.md`. This note covers only the crop model work in lane A's checkout (`D:\nasa_space_apps`, branch `lane/a-ml`).

## Where things stand

**Done and verified**
- Manus's crop model (v2, `ml/crop_model/crop_suitability_v2.npz`) was retrained locally as **v3** to remove rain-only false alarms. The app now uses v3.
  - Files: `ml/crop_model/crop_suitability_v3.npz`, `crop_engine_v3.py`, `metrics_v3.json`
  - How it was chosen: `ml/crop_model/retrain/README.md`
- What changed: same XGBoost and settings as Manus, plus two things.
  1. Crop-aware rain-only counter-examples up to 250 mm.
  2. A documented rain gate in rain-only mode: the score is 0 below 100 mm a year and reaches full strength at 200 mm for wheat and barley, 250 mm for other crops. Irrigated scores are never changed.
- Numbers on the same held-out suite (5 folds of 10 x 10 degree blocks):

  | | v2 | v3 |
  |---|---|---|
  | Held-out AUC | 0.904 | 0.898 |
  | Rain-only false alarms on held-out dry land (crops per place) | 2.7 | 0.7 |
  | Egypt FAOSTAT AUC (model trained without Egypt) | 0.917 | 0.933 |

  Cost: at 150 to 300 mm, about a fifth fewer real rain-fed crops are found.
- Egypt with v3, rain only: nothing reaches 50 below 100 mm. Above that, only barley does, on the north-west coast (Marsa Matruh) and in North Sinai, where Egypt really grows it on rain.
- Rebuilt: `ml/outputs/farming_EGY.json` (`python run.py crop-model`, 3 min) and `ml/outputs/validation.json` (`python ml/validate.py`; 8 of 8 crop checks pass).
- Tests: `python run.py check` gives 59 passed, 1 skipped. New tests in `tests/test_crop_model.py` cover the rain gate and "no rain-only false alarms in Egypt".
- App, checked in the browser on real data (MOCK=0):
  - all four tabs, both water modes and the Decisions lists
  - opening a place from a list, then "Back to the list"
  - the methods panel and the 9-step tour, with no JS errors
  - API sweep: every endpoint answers, with plain-sentence errors, and the answers validate against the schemas
- Fixed in `app/` (lane B was told in its inbox in `TASKS.md`):
  - the legend no longer says "cannot grow" for a score of 0
  - "stable" was removed from the change legend
  - the tour's food step uses temperate fruit (it asked for "apple", which the model does not have)
- Docs: `ml/model_card.md` (v3 section), `ml/crop_model/README.md`, `docs/DECISIONS.md`, `docs/METHODS.md`, `docs/LOG.md`, `TASKS.md` (A10).

**Not done**
- Nothing is committed. Commit only lane A's files plus the `app/` edits above. Another session added `ml/crosscheck.py`, `docs/CROSSCHECK.md` and `tests/test_crosscheck.py`: leave them to it.
- Lane C: `docs/REFERENCES.md` still needs the IFPRI, FAOSTAT, Manus and XGBoost citations (REQUEST lines in the lane C inbox).
- Optional, lane B: `/api/meta` and `/api/predictions` still serve the Friday skeleton ("FAKE DATA"). The app never calls them.
- Known limit, documented: the NASA POWER rain record jumps around 2015 over Egypt. Some 2035 crop changes are large (for example sugar beet +33 in one desert cell) because each feature's trend is extended. The app shows a rain caution next to these changes.

## How to rebuild anything

    python -m pip install xgboost                 # training only; the app needs numpy only
    python ml/crop_model/retrain/train_v3.py      # about 20 s: model + metrics_v3.json
    python run.py crop-model                      # about 3 min: ml/outputs/farming_EGY.json
    python ml/validate.py                         # ml/outputs/validation.json
    python run.py check

## Leftovers from the previous session (can be deleted)

`handoff/audit_scratch/` and the two `handoff/*.js` workflow scripts are from an audit that never finished. Nothing in them is needed. They are gitignored.
