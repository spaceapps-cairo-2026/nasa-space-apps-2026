# How to connect a crops / farmland model to the app

The Crops, Farmland and Decisions tabs contain no model. They read ONE answer:

    GET /api/farming?country=EGY   ->   the file ml/outputs/farming_EGY.json

Today that file is written by `ml/farming.py` (a simple FAO ECOCROP calculator, so the tabs can be
demoed). To use your trained model instead: **make your model write `ml/outputs/farming_EGY.json`
in the format below, then run the check.** No change to `app/` or `api/` is needed; reload the page
and the tabs show your model. (If the file is missing, the API falls back to
`contracts/fixtures/farming_EGY.json`.)

Full format: `contracts/farming.schema.json` (v0.4). Real example: `ml/outputs/farming_EGY.json`.

## Three steps

1. Write the file (the smallest valid file is under "The least you need").
2. Check it. This tells you in plain words what is wrong, before the app reads it:

       python run.py farming-check                  (checks ml/outputs/farming_EGY.json)
       python run.py farming-check my_file.json     (checks any other file)

   `ERROR` = the app would break or show wrong numbers, fix it. `NOTE` = it works, but that part of
   the app is hidden; decide if that is what you want.
3. Look at it: `python run.py api`, open http://localhost:8000, tabs Crops, Farmland, Decisions.

`ml/farming.py` will not overwrite your file: it skips `ml/outputs/farming_EGY.json` when another
model wrote it (it only replaces it with `--force`).

## The grid

The map is a regular grid. Cell `k = i * ncols + j` (row `i` from the south, column `j` from the
west) is centered at `lat = lat0 + i * dlat`, `lon = lon0 + j * dlon`. Every per-cell list has
`nrows * ncols` values in that order; use `null` where there is no value. Use the same grid as the
example (Egypt: lat0 22.0, lon0 25.0, dlat 0.5, dlon 0.625, 21 rows, 17 columns) and copy `inside`
from it unless your model uses another grid.

## The least you need

| Field | Meaning |
|---|---|
| `version` | `"0.4"` |
| `region` | `{"id": "EGY", "name": "Egypt", "bbox": [west, south, east, north]}` |
| `grid` | `{"lat0", "lon0", "dlat", "dlon", "nrows", "ncols"}` |
| `method` | one or two sentences describing your model, shown in the app under "How we know" |
| `horizons` | the years you give scores for, first = now. One year is enough: `[2025]`. The app makes one button per year |
| `inside` | string of `"1"`/`"0"`, one character per cell: does the cell touch the country |
| `crops` | list of `{"id", "name"}`; ids are lowercase with underscores (`wheat`, `date_palm`) |
| `suitability` | `{"irrigated": {crop_id: [grid for each year in horizons]}}`, and / or `"rainfed"`. Each grid is a list of **whole numbers 0 to 100** (100 = ideal), `null` outside the country |

If your model gives something else than a 0 to 100 score per cell (for example a best-crop label or
a yield), convert it first: for a probability multiply by 100 and round; for a yield divide by the
best yield of that crop. Say how in `method`.

## Optional, each one switches a part of the app on

| Field | What the app shows with it |
|---|---|
| `suitability.rainfed` (or `.irrigated`) | the second "Water" button; without it that button is switched off |
| more than one year in `horizons` | the year buttons, "Change by ..." and the gaining / losing lists |
| `years_to_heat_limit` | `{crop_id: grid}` of years until the crop gets too hot (99 = safe, null = not applicable): the "Years to heat limit" view and that Decisions list |
| `temp_now_c`, `rain_now_mm`, `temp_trend_per_decade` | per-cell climate lines in the place panel (`climate_period`, e.g. `"2016 to 2025"`, labels the first) |
| `evidence` | string, one character per cell: `S` strong, `M` moderate, `N` not proven, `-` no data: the evidence badges |
| `suitable_threshold` | score at which a crop "fits" a place (50 if you leave it out) |
| `source` | short text shown as "Source: ..." (for example your training data) |
| `score_note` | how to read a score, in plain words, shown in the place panel |
| per crop: `scientific_name`, `season_months`, `temp_opt_c: [lo, hi]`, `temp_abs_c: [lo, hi]` | the crop line under the crop picker |
| `suitability_10_low` / `_high`, `best_start_month` | uncertainty tooltip and the season of each crop |

## Tests

    python run.py check

`tests/test_api_v03.py` has common-sense checks written for the FAO calculator (no apples in Aswan,
no rain-fed wheat in Egypt). If your model disagrees, look at why first; change the test only if the
model is right. The app's "How we know" panel (check 4 and the data line) also describes the FAO
calculator; tell lane A when your model replaces it so those texts are updated.

## Another format?

If your model already outputs something different, tell lane B (Eyad) the shape and the UI will be
adapted instead.
