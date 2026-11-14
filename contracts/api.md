# API contract (v0.5)

Owned by lane A. Lane B implements it in `api/main.py`. The app only talks to these endpoints.

Start it: `python run.py mock` (fixtures, no internet) or `python run.py api` (real data), then open http://localhost:8000. Interactive docs: http://localhost:8000/docs

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{"status": "ok", "mock": true/false, "version": "0.5"}` |
| GET | `/api/variables` | the measurement picker: `{version, period, start_year, end_year, min_range_years, variables: [{code, name, unit, source, point, region, world}]}` |
| GET | `/api/trend/point?lat=&lon=&variable=T2M&start_year=&end_year=` | `trend_point`: one place, yearly series, trend line, rate, confidence, sentence |
| GET | `/api/trend/region?lat_min=&lat_max=&lon_min=&lon_max=&variable=T2M&country=&start_year=&end_year=` | `trend_region`: trend map for every grid cell in the box (compact grid), counts, region average series. `country` is optional (ISO 3 letter code, for example `EGY`): see "Country maps" below |
| GET | `/api/trend/world?variable=T2M&stride=2&start_year=&end_year=` | `trend_world`: whole Earth overview (compact grid). `stride` 1, 2, 4 or 8 = keep every n-th cell |
| GET | `/` | the static app in `app/` (if the folder exists) |
| GET | `/api/meta`, `/api/predictions`, `/api/items/{id}` | old v0.2 PredictionBundle, kept so nothing breaks; not used by F1 |

Exact shapes: `contracts/trend.schema.json`. Examples made by the real engine: `contracts/fixtures/trend_point.json` (Cairo), `trend_region.json` (Egypt), `trend_world.json` (stride 8), `variables.json`.

## Year range (`start_year`, `end_year`, new in v0.5)

Every trend endpoint takes optional `start_year` and `end_year`. The trend (amount, rate, luck percentage, level, map) is then measured over those years only. Left out = the whole record, 2001 to 2025.

- The range must be inside 2001 to 2025 and at least **10 years** long (`min_range_years` in `/api/variables`). Anything else answers 400 with a sentence to show.
- A place needs data for at least 80% of the chosen years, otherwise it is "no data".
- `series` and `mean_series` always contain **every** year, so the chart can show the full record and highlight the chosen years. `trend_line` and `mean_trend_line` cover only the chosen years.
- Each `trend` object says what it covers: `period` ("2008-2022"), `start_year`, `end_year`. Region and world answers have `period`, `start_year`, `end_year` at the top level too.
- **Total change over the chosen years:** `change_total`, with `change_low` and `change_high` (95% range), in the variable's unit. It is the rate times the number of years between the first and last year. `slope_per_decade` is still there: the app shows the total change and the rate per decade side by side as the two headline numbers. For a map cell: total change = `slope_per_decade` x (`end_year` - `start_year`) / 10.
- **Shorter ranges prove less.** With the same real rate of change, the engine proves it in about 87% of cases over 25 years, 56% over 20, 25% over 15 and 9% over 10. False alarms stay near 5% at every length. So a short range that says "not proven" is normal: say so in the app, never "no change".

## Measurements (`variable`)

| Code | Name | Unit | Point | Region map | World overview |
|---|---|---|---|---|---|
| `T2M` | average air temperature | C | yes | yes | yes |
| `T2M_MAX` | daily maximum air temperature | C | yes | yes | only after the bulk download |
| `T2M_MIN` | daily minimum air temperature | C | yes | no | no |
| `PRECTOTCORR` | precipitation | mm/day | yes | yes | only after the bulk download |
| `GWETTOP` | topsoil wetness | fraction (0 to 1) | yes | yes | only after the bulk download |
| `GWETROOT` | root zone soil wetness | fraction (0 to 1) | yes | yes | only after the bulk download |
| `RH2M` | relative humidity | % | yes | yes | only after the bulk download |

## How to read an answer

- **How much:** `change_total` over the chosen years (with `change_low`, `change_high`), and the rate `slope_per_decade` (with `slope_low`, `slope_high`), in the variable's unit. The low and high values are the 95% range.
- These are two different questions. The **luck percentage** (`p`) answers "is there a change at all?" and decides the level. The **95% range** answers "how big is the change?". The level is only the luck percentage in words; it is not a second measure of confidence.
- **Is it real:** `level` and `level_name`.

| `level` | `level_name` | Rule | Suggested map color |
|---|---|---|---|
| 2 | strong evidence | below 0.01 | full color (red rising, blue falling; for rain and soil the app may flip colors) |
| 1 | moderate evidence | below 0.05 | lighter color |
| 0 | not proven | everything else | grey |
| -1 | no data | data for fewer than 80% of the chosen years (20 of the full 25), or no measurement there | transparent |

- On a **map** the rule is applied to `q` (false discovery rate over all cells of that map). For a **single place** it is applied to `p`.
- `p` is how often a trend at least this strong shows up when nothing is really changing. It is **not** "the chance the trend is true". Show the level; show `p` or `q` on hover. Never show "87% true".
- As a percentage: `p` x 100 = "with nothing really changing, a trend this strong appears by luck this often". The app shows it as "Could this be luck? 2.7%" and `sentence` uses the same words. Never turn it around into "97.3% real".
- `slope_low` and `slope_high` are the 95% range. 95% is the confidence level chosen for every place, not a result: ranges built this way contain the true rate about 95 times out of 100. A range that includes 0 means not proven.
- Say "not proven", never "no change".
- `sentence` is ready to show as is. `caution` (may be null) must be shown when present.
- Every precipitation answer has a `caution`: in this NASA POWER rain record rain jumps around 2015 in many places at once (across Egypt about 3 times higher after 2015), which looks like a change in how the record is made. Never present a rain trend without it.
- A series that never changes (soil wetness over the sea is a constant fill value of 1) is no data (`level` -1), not "not proven".
- **Region grid:** `grid.slope_per_decade[i][j]` belongs to the cell centered at `grid.lats[i]`, `grid.lons[j]`; the cell is `lat_step` x `lon_step` degrees. `null` = no data. Draw each cell as a rectangle.
- The region is a **box**. If the user picked a country, send `country=<ISO>` as well (see "Country maps") and clip the drawn cells to the border.
- `data_from`: `repo` (Egypt, in git), `cache` (fetched before), `nasa` (fetched just now).

## Country maps (`country=`, new in v0.4)

Without `country`, everything is computed over the whole box: sea and neighbouring countries are tested and counted too.
With `country=EGY` (the box must still be sent, it says which data to load):

- cells that do not touch the country come back as no data (`level` -1, `slope_per_decade` null);
- `q` (the correction for testing many places) is computed over the country's cells only, so levels can differ from the box answer;
- `summary`, `mean_series`, `mean_trend`, `sentence` and `mean_sentence` describe the country, and the sentences name it ("averaged over Egypt");
- the answer carries `"country": {"iso": "EGY", "name": "Egypt"}` (null without the parameter).

A cell touches the country when at least 8% of it is inside the border (the same rule the app uses to clip cells). Borders: `app/data/regions/<ISO>.geojson` when present, else `app/data/borders_50m.geojson` (Natural Earth). Example on Egypt, air temperature, with the box the app sends (lat 22 to 31.586, lon 24.7 to 36.866): the box has 380 cells and 161 proven warming; Egypt itself has 323 cells and 84 proven warming.

## Speed and errors

| Request | Time |
|---|---|
| Egypt, or anything fetched before | under 0.1 s |
| New point | about 1.5 s (one NASA request, then cached) |
| New region | about 5 s per 10 x 10 degree tile, tiles in parallel; show "fetching NASA data for this region..." |
| World overview | about 5 s the first time, then instant |

| Status | Meaning | `detail` |
|---|---|---|
| 400 | bad request (unknown measurement or country, impossible box, no map for this measurement) | a plain sentence that can be shown to the user as is |
| 413 | region needs more than 12 blocks of NASA data that are not cached yet | a plain sentence asking for a smaller area, can be shown as is |
| 422 | missing or non numeric parameter | FastAPI's standard message |
| 502 | NASA could not be reached and the data is not cached | a plain sentence, can be shown as is |

`/api/variables` says what exists before you ask: `region: false` means no trend map for that measurement, `world: false` means no whole Earth overview yet. The app should use these flags to disable the control instead of waiting for a 400.

## Mock mode

`MOCK=1` (`python run.py mock`): every trend endpoint returns its fixture whatever the parameters are. `MOCK=0` (`python run.py api`): real answers.

## Python functions behind the endpoints (lane B calls these, never edits them)

```python
import sys; sys.path.insert(0, "ml")
import live
live.point_trend("T2M", 30.04, 31.24)             # -> trend_point
live.region_trend("T2M", 22, 32, 25, 35)          # -> trend_region  (lat_min, lat_max, lon_min, lon_max)
live.region_trend("T2M", 22, 32, 25, 35, country="EGY")   # the same, counted inside Egypt's border only
live.world_trend("T2M", stride=2)                 # -> trend_world
live.variables()
# Errors: live.BadRequest (400), live.RegionTooLarge (413), live.SourceUnavailable (502)
```
The engine itself (arrays in, arrays out) is `ml/trends.py`: `trend_grid`, `trend_one`, `fdr_bh`, `confidence_levels`, `change_point`.

## Rules

- Adding an optional field is a minor bump. Renaming or removing a field is a major bump and needs a team message.
- The app must ignore fields it does not know, so lane A can add fields without breaking lane B.

## Lane B additions (for lane A to review)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/farming?country=EGY` | Farming outlook for a focus country (F2 to F4): suitability of 40 crops now (2025) / 2030 / 2035, irrigated and rain-fed, with the 95% range for 2035, the warming evidence per cell, where farmland exists today and where the climate is outside the model's training (`farmland`, `outside_training`, new in farming schema v0.5). Shape: `contracts/farming.schema.json`. Built by `python run.py crop-model` from the trained crop model in `ml/crop_model/` (model card: `ml/model_card.md`); `python ml/farming.py` (FAO ECOCROP calculator, also has years to each crop's heat limit) writes the same shape and stays as the fixture. Other countries: 404 "Farming analysis is available for: Egypt." |
| GET | `/api/validation` | Numbers for the app's "How we know" panel (F5): GISTEMP cross-check, false alarm rate of the D1 engine, effect of FDR on Egypt, farming common-sense checks, limitations. Built by `python ml/validate.py` (uses `ml/trends.py`). |
