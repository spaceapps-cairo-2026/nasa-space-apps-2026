# API contract (v0.3)

Owned by lane A. Lane B implements it in `api/main.py`. The app only talks to these endpoints.

Start it: `python run.py mock` (fixtures, no internet) or `python run.py api` (real data), then open http://localhost:8000. Interactive docs: http://localhost:8000/docs

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{"status": "ok", "mock": true/false, "version": "0.3"}` |
| GET | `/api/variables` | the measurement picker: `{version, period, variables: [{code, name, unit, source, point, region, world}]}` |
| GET | `/api/trend/point?lat=&lon=&variable=T2M` | `trend_point`: one place, yearly series, trend line, rate, confidence, sentence |
| GET | `/api/trend/region?lat_min=&lat_max=&lon_min=&lon_max=&variable=T2M` | `trend_region`: trend map for every grid cell in the box (compact grid), counts, region average series |
| GET | `/api/trend/world?variable=T2M&stride=2` | `trend_world`: whole Earth overview (compact grid). `stride` 1, 2, 4 or 8 = keep every n-th cell |
| GET | `/` | the static app in `app/` (if the folder exists) |
| GET | `/api/meta`, `/api/predictions`, `/api/items/{id}` | old v0.2 PredictionBundle, kept so nothing breaks; not used by F1 |

Exact shapes: `contracts/trend.schema.json`. Examples made by the real engine: `contracts/fixtures/trend_point.json` (Cairo), `trend_region.json` (Egypt), `trend_world.json` (stride 8), `variables.json`.

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

- **How much:** `slope_per_decade` in the variable's unit, with `slope_low` and `slope_high` (95% range).
- **Is it real:** `level` and `level_name`.

| `level` | `level_name` | Rule | Suggested map color |
|---|---|---|---|
| 2 | strong evidence | below 0.01 | full color (red rising, blue falling; for rain and soil the app may flip colors) |
| 1 | moderate evidence | below 0.05 | lighter color |
| 0 | not proven | everything else | grey |
| -1 | no data | fewer than 20 valid years, or no measurement there | transparent |

- On a **map** the rule is applied to `q` (false discovery rate over all cells of that map). For a **single place** it is applied to `p`.
- `p` is how often a trend at least this strong shows up when nothing is really changing. It is **not** "the chance the trend is true". Show the level; show `p` or `q` on hover. Never show "87% true".
- Say "not proven", never "no change".
- `sentence` is ready to show as is. `caution` (may be null) must be shown when present.
- **Region grid:** `grid.slope_per_decade[i][j]` belongs to the cell centered at `grid.lats[i]`, `grid.lons[j]`; the cell is `lat_step` x `lon_step` degrees. `null` = no data. Draw each cell as a rectangle.
- The region is a **box**. If the user picked a country, the app clips the cells to the border.
- `data_from`: `repo` (Egypt, in git), `cache` (fetched before), `nasa` (fetched just now).

## Speed and errors

| Request | Time |
|---|---|
| Egypt, or anything fetched before | under 0.1 s |
| New point | about 1.5 s (one NASA request, then cached) |
| New region | about 5 s per 10 x 10 degree tile, tiles in parallel; show "fetching NASA data for this region..." |
| World overview | about 5 s the first time, then instant |

| Status | Meaning | `detail` |
|---|---|---|
| 400 | bad request (unknown variable, impossible box) | what to fix |
| 413 | region needs more than 12 new tiles | ask the user to zoom in |
| 422 | missing or non numeric parameter | FastAPI's standard message |
| 502 | NASA could not be reached and the data is not cached | show "NASA data is not reachable right now" |

## Mock mode

`MOCK=1` (`python run.py mock`): every trend endpoint returns its fixture whatever the parameters are. `MOCK=0` (`python run.py api`): real answers.

## Python functions behind the endpoints (lane B calls these, never edits them)

```python
import sys; sys.path.insert(0, "ml")
import live
live.point_trend("T2M", 30.04, 31.24)             # -> trend_point
live.region_trend("T2M", 22, 32, 25, 35)          # -> trend_region  (lat_min, lat_max, lon_min, lon_max)
live.world_trend("T2M", stride=2)                 # -> trend_world
live.variables()
# Errors: live.BadRequest (400), live.RegionTooLarge (413), live.SourceUnavailable (502)
```
The engine itself (arrays in, arrays out) is `ml/trends.py`: `trend_grid`, `trend_one`, `fdr_bh`, `confidence_levels`, `change_point`.

## Rules

- Adding an optional field is a minor bump. Renaming or removing a field is a major bump and needs a team message.
- The app must ignore fields it does not know, so lane A can add fields without breaking lane B.
