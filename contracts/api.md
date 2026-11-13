# API contract (v0.3)

Owned by lane A. Lane B implements it in `api/main.py`. The app only talks to these endpoints.
Shapes are defined in JSON Schema: `contracts/trend.schema.json` (F1, new in v0.3) and
`contracts/prediction.schema.json` (v0.2 bundle, kept so nothing breaks).

## F1 Trend explorer endpoints (v0.3)

| Method | Path | Returns (schema `$defs` name) |
|---|---|---|
| GET | `/api/variables` | `VariableList`: every measurement the picker can offer, with a simple definition |
| GET | `/api/regions` | `RegionList`: regions that have a precomputed map (for now: Egypt) |
| GET | `/api/trend/point?lat=30.04&lon=31.24&var=T2M&name=Cairo` | `TrendResult` for one place, computed live from NASA POWER (cached) |
| GET | `/api/trend/region?region=egypt&var=T2M` | `RegionTrend`: one trend per grid cell, with FDR q-values |
| GET | `/api/trend/cell?region=egypt&cell=p_30.0_31.25&var=T2M` | `TrendResult` for one grid cell of a region map (same shape as a point) |

Errors: unknown `var`, `region` or `cell` returns 404 with `{"detail": "..."}`. A point outside every
region still works (points are global). The app shows "regional analysis available for: Egypt"
using `/api/regions`.

### How the pieces fit
1. The app loads `/api/variables` and `/api/regions` once at start.
2. User clicks anywhere on the globe: app calls `/api/trend/point` and shows chart + numbers + sentence.
3. User opens a region map: app calls `/api/trend/region`, colors each cell by `slope_per_decade`,
   grey when `confidence` is `not_proven`.
4. User clicks a cell on that map: app calls `/api/trend/cell` and shows the same panel as in step 2.

### Field meanings (plain words)
- `series`: one value per year (the average of that year's months). Using yearly averages removes
  the summer/winter cycle so it cannot be mistaken for a trend.
- `trend.slope_per_decade`: how much the value changes in 10 years, in the variable's own unit.
- `trend.ci_low`, `trend.ci_high`: the range the true rate probably lies in (95% confidence interval).
- `trend.p`: the chance of seeing a trend at least this strong if nothing were really changing.
  It is NOT the chance that the trend is true. Never show it as "87% true".
- `trend.q`: the p-value corrected for testing many cells at once (false discovery rate). Only on
  region maps; `null` for a single point.
- `trend.confidence`: `strong`, `moderate` or `not_proven`. Thresholds are decision D2; until then
  see "Provisional thresholds" below. Never write "no change"; write "not proven".
- `trend.direction`: `increasing`, `decreasing` or `no_clear_trend` (only when not proven).
- `trend.change_start_year`: year the change seems to begin, or `null`.
- `trend.line`: two points (first and last year) to draw the trend line on the chart.
- `sentence`: a plain summary built only from the numbers above.
- `caution`: a warning to show next to the result, or `null` (example: rainfall over hyper-arid desert).

### Provisional thresholds (until D2)
- Point: `strong` if p < 0.01, `moderate` if p < 0.05, else `not_proven`.
- Region cell: same, but using q instead of p.

## Python function the API calls (lane A provides, lane B imports, never edits)

```python
from ml.trends import point_trend, region_trend, cell_trend, VARIABLES, REGIONS

point_trend(lat: float, lon: float, var: str, name: str | None = None) -> dict   # TrendResult
region_trend(region: str, var: str) -> dict                                        # RegionTrend
cell_trend(region: str, cell: str, var: str) -> dict                               # TrendResult
VARIABLES: list[dict]   # VariableList["variables"]
REGIONS: list[dict]     # RegionList["regions"]
```
Each raises `KeyError` for an unknown variable, region or cell (the API turns that into 404).
With `MOCK=1` the API serves `contracts/fixtures/trend_*.json` instead of calling these.

## Fixtures (fake but valid, for building the app before the engine is final)
- `contracts/fixtures/variables.json`, `regions.json`
- `contracts/fixtures/trend_point_cairo_T2M.json`
- `contracts/fixtures/trend_region_egypt_T2M.json`
Built by `python ml/make_trend_fixtures.py` from the real NASA POWER download, with a placeholder
method (D1 is not decided yet). Every fixture says so in `method`.

## Old v0.2 endpoints (kept until the app moves to v0.3)

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
