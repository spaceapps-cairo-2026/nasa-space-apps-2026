# API contract (v0.3, DRAFT by lane B for lane A to review)

Owned by lane A. This draft follows `PROJECT_PLAN.md` sections 5 and 6 (trends worldwide by live
fetch, maps as a compact grid). Lane A may change it; lane B adapts. Lane B implements the endpoints
in `api/main.py`; the app only talks to these endpoints.
Shapes are defined in JSON Schema: `contracts/trend.schema.json` (F1) and
`contracts/prediction.schema.json` (old v0.2 bundle, kept so nothing breaks).

## F1 Trend explorer endpoints

| Method | Path | Returns (schema `$defs` name) |
|---|---|---|
| GET | `/api/variables` | `VariableList`: every measurement the picker can offer, with a simple definition |
| GET | `/api/regions` | `RegionList`: focus countries for the farming features (F2 to F4); trends do not need it |
| GET | `/api/trend/point?lat=30.04&lon=31.24&var=T2M&name=Cairo` | `TrendResult` for one place, live from NASA POWER (cached) |
| GET | `/api/trend/region?var=T2M&south=22&north=32&west=24.7&east=36.9&name=Egypt` | `GridTrend` for a box anywhere on Earth: live fetch with `region_monthly()` (first time 5 to 40 s, then instant) |
| GET | `/api/trend/world?var=T2M` | `GridTrend` for the whole Earth (precomputed from `data/processed/world/<VAR>_annual.npz`); 404 for a variable without a world file |
| GET | `/api/trend/cell?var=T2M&lat=30.0&lon=31.25` | `TrendResult` for one grid cell (same shape as a point), so the chart matches the map |

Errors: unknown `var` returns 404; an invalid box returns 422; a box too large for live fetch
(more than 2,500 square degrees, e.g. Russia, Canada, USA) returns 413 with a short message. All
errors are `{"detail": "..."}` in plain words; the app shows `detail` to the user.

### How the pieces fit
1. The app loads `/api/variables` once at start, then `/api/trend/world` for the overview layer
   (whole Earth colored, visible when zoomed out).
2. Click anywhere: `/api/trend/point`, then chart + numbers + sentence.
3. Select a country: the app sends the country's bounding box to `/api/trend/region`, shows
   "fetching NASA data" while waiting, then draws the cells cut to the country's border.
4. Click a cell of that map: `/api/trend/cell` with the cell's center.

## The compact grid (`GridTrend`)
A map is a regular grid, not one JSON object per cell. Row `i` (south to north) and column `j`
(west to east) is the cell centered at:

    lat = grid.lat0 + i * grid.dlat        lon = grid.lon0 + j * grid.dlon

Its value is at index `k = i * grid.ncols + j` in each of these flat arrays:
- `slope_per_decade[k]`: rate of change per 10 years in the variable's unit, `null` = no data.
- `q[k]`: p-value corrected for testing many cells at once (Benjamini-Hochberg over the cells
  of this response), `null` = no data.
- `confidence[k]`: one character per cell, `S` strong, `M` moderate, `N` not proven, `-` no data.
  Direction is the sign of `slope_per_decade` and only means something when not `N`.

NASA POWER grid: `dlat = 0.5`, `dlon = 0.625`, centers on multiples of those steps from
(-90, -180), so every response lines up with every other one.

## Farming outlook (F2 farmland, F3 crops, F4 decisions)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/farming?country=EGY` | `FarmingOutlook` for a focus country (precomputed by `python ml/farming.py`); other countries: 404 "Farming analysis is available for: Egypt." |

`FarmingOutlook` uses the same grid layout as `GridTrend` (`grid`, flat arrays, index `k = i * ncols + j`):
- `inside[k]`: `"1"` if the cell touches the country.
- `horizons`: `[2025, 2030, 2035]` (now, +5, +10 years, "if current trends continue").
- `crops`: id, name, scientific name, season length in months, FAO source link, optimal and absolute temperature.
- `suitability[mode][crop]`: three flat grids (one per horizon) of 0 to 100, `mode` is `irrigated` or `rainfed`.
- `suitability_10_low` / `suitability_10_high[mode][crop]`: +10 years using the low and high end of the trend's 95% range.
- `best_start_month[mode][crop]`: first month (0 = January) of the best growing season now.
- `years_to_heat_limit[crop]`: years until the hottest month of that season reaches the crop's absolute heat limit at the cell's current warming rate (irrigated, capped at 99, null when not warming or not suitable).
- `temp_now_c`, `rain_now_mm`, `temp_trend_per_decade`, `rain_trend_mm_per_decade`: the climate behind the scores.
- `evidence[k]`: confidence of the cell's temperature trend (`S`, `M`, `N`, `-`): future changes in `N` cells rest on a trend that is not proven.
- `suitable_threshold`: a crop "fits" a place at this score or above (50).

## Field meanings for a single place (`TrendResult`)
- `series`: one value per year (the average of that year's months). Yearly averages remove the
  summer/winter cycle so it cannot be mistaken for a trend.
- `trend.slope_per_decade`: how much the value changes in 10 years, in the variable's own unit.
- `trend.ci_low`, `trend.ci_high`: the range the true rate probably lies in (95% interval).
- `trend.p`: the chance of seeing a trend at least this strong if nothing were really changing.
  It is NOT the chance that the trend is true. Never show it as "87% true".
- `trend.q`: corrected p-value when the place belongs to a map; `null` for a single point.
- `trend.confidence`: `strong`, `moderate` or `not_proven` (thresholds are D2). Never write
  "no change"; write "not proven".
- `trend.direction`: `increasing`, `decreasing` or `no_clear_trend` (only when not proven).
- `trend.change_start_year`: year the change seems to begin, or `null`.
- `trend.line`: two points (first and last year) to draw the trend line.
- `sentence`: plain summary built only from the numbers above. `caution`: warning or `null`.

### Provisional thresholds (until D2)
- Point: `strong` if p < 0.01, `moderate` if p < 0.05, else `not_proven`.
- Map cell: same, using q instead of p.

## Python functions the API calls (lane A provides, lane B imports, never edits)

```python
from ml.trends import point_trend, region_trend, world_trend, cell_trend, VARIABLES, REGIONS

point_trend(lat: float, lon: float, var: str, name: str | None = None) -> dict             # TrendResult
region_trend(var: str, south: float, north: float, west: float, east: float,
             name: str | None = None) -> dict                                                # GridTrend
world_trend(var: str) -> dict                                                                # GridTrend
cell_trend(var: str, lat: float, lon: float) -> dict                                         # TrendResult
VARIABLES: list[dict]   # VariableList["variables"]
REGIONS: list[dict]     # RegionList["regions"] (focus countries for farming)
```
`KeyError` for an unknown variable or a missing world file (API answers 404), `ValueError` for a
bad box (422). With `MOCK=1` the API answers from `contracts/fixtures/` instead.

## Fixtures (fake method, real data)
Built by `python ml/make_trend_fixtures.py` from the NASA POWER data in the repo:
- `variables.json`, `regions.json`
- `trend_point_cairo_T2M.json` (TrendResult)
- `trend_region_egypt_T2M.json` (GridTrend, Egypt box)
- `trend_world_T2M.json` (GridTrend, whole Earth). In MOCK mode the API also cuts any box out of
  this file, so the app can show a map for any country before the engine exists.
The method in every fixture is a placeholder (D1 not decided) and says so in `method`.

## Old v0.2 endpoints (kept until nothing uses them)

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{"status": "ok", "mock": true/false, "version": "..."}` |
| GET | `/api/meta` | `{challenge, model}` from the bundle (no items) |
| GET | `/api/predictions?min_score=0&label=` | full `PredictionBundle`, items filtered |
| GET | `/api/items/{id}` | one item, 404 if missing |
| GET | `/` | the static app in `app/` |

## Rules
- Adding an optional field is a minor bump (0.3 to 0.4). Renaming or removing a field is a major
  bump and needs a team message.
- The app must ignore fields it does not know, so lane A can add fields without breaking lane B.
