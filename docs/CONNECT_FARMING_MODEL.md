# How to connect a crops / farmland model to the app

The Crops, Farmland and Decisions tabs contain no model. They read ONE answer:

    GET /api/farming?country=EGY   ->   the file ml/outputs/farming_EGY.json

Today that file is written by `ml/farming.py` (a simple FAO ECOCROP calculator, so the tabs can be
demoed). To use your trained model instead: **make your model write `ml/outputs/farming_EGY.json`
in the format below.** No change to `app/` or `api/` is needed; reload the page and the tabs show
your model. (If the file is missing, the API falls back to `contracts/fixtures/farming_EGY.json`.)

Full format: `contracts/farming.schema.json`. Real example: `ml/outputs/farming_EGY.json`.

## The format in plain words

The map is a regular grid. Cell `k = i * ncols + j` (row `i` from the south, column `j` from the
west) is centered at `lat = lat0 + i * dlat`, `lon = lon0 + j * dlon`. Every per-cell list has
`nrows * ncols` values in that order; use `null` where there is no value.

| Field | Meaning | Used by |
|---|---|---|
| `version` | `"0.3"` | |
| `region` | `{"id": "EGY", "name": "Egypt", "bbox": [west, south, east, north]}` | |
| `grid` | `{"lat0", "lon0", "dlat", "dlon", "nrows", "ncols"}` (Egypt today: 22.0, 25.0, 0.5, 0.625, 21, 17) | all tabs |
| `method` | one sentence describing your model (shown in the app under "How we know") | Crops panel |
| `horizons` | years shown by the Now / 2030 / 2035 buttons, e.g. `[2025, 2030, 2035]` | Crops, Farmland |
| `inside` | string of `"1"`/`"0"`, one character per cell: does the cell touch the country | all tabs |
| `crops` | list of `{"id", "name", "scientific_name", "season_months", "temp_opt_c": [lo, hi], "temp_abs_c": [lo, hi]}` | crop picker, info line |
| `suitability` | `{"irrigated": {crop_id: [grid_now, grid_2030, grid_2035]}, "rainfed": {...}}`, each grid a list of integers 0 to 100 | Crops map, Farmland, Decisions |
| `suitability_10_low` / `_high` | optional: same as the last horizon, lower and upper end of your uncertainty | panel tooltip |
| `best_start_month` | optional: `{mode: {crop_id: grid}}`, 0 = January, start of the best season now | panel "season" |
| `years_to_heat_limit` | optional: `{crop_id: grid}`, years until the crop becomes too hot (99 = safe, null = not applicable) | "Years to heat limit" view, Decisions |
| `temp_now_c`, `rain_now_mm`, `temp_trend_per_decade` | per-cell climate shown in the panel | place panel |
| `evidence` | string, one character per cell: `S` strong, `M` moderate, `N` not proven, `-` no data (strength of the warming trend) | badges |
| `suitable_threshold` | score at which a crop "fits" a place (50 today) | Farmland counts, Decisions |

Scores are 0 to 100 (100 = ideal). Crop ids are lowercase with underscores (`wheat`, `date_palm`).

## Check it

    python -m pytest tests/test_api_v03.py      (the format test must pass)
    python run.py api                            (then open http://localhost:8000, tabs Crops, Farmland, Decisions)

`tests/test_api_v03.py` also has common-sense checks written for the FAO calculator (no apples in
Aswan, no rain-fed wheat in Egypt). If your model disagrees, look at why first; change the test
only if the model is right.

## Another format?

If your model already outputs something different, tell lane B (Eyad) the shape and the UI will be
adapted instead.
