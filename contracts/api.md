# API contract (v0.2)

Owned by lane A. Lane B implements it in `api/main.py`. Lane B's app only talks to these endpoints.

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{"status": "ok", "mock": true/false, "version": "0.1"}` |
| GET | `/api/meta` | `{challenge, model}` from the bundle (no items) |
| GET | `/api/predictions?min_score=0&label=` | full `PredictionBundle` (see schema), items filtered |
| GET | `/api/items/{id}` | one item, 404 if missing |
| GET | `/` | the static app in `app/` |

Source of data:
- `MOCK=1`: `contracts/fixtures/sample_predictions.json`
- `MOCK=0`: `ml/outputs/predictions.json` (written by `ml/predict.py`)

Rules:
- Adding an optional field is a minor bump (0.1 to 0.2). Renaming or removing a field is a major bump and needs a team message.
- The app must ignore fields it does not know, so lane A can add fields without breaking lane B.
