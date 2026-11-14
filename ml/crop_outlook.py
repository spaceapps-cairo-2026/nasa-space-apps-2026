"""Lane A: farming outlook for a focus country from the trained crop model (tasks A5 to A8, decisions D4 to D7).

    python run.py crop-model            Egypt: writes ml/outputs/farming_EGY.json (about 3 minutes)
    python run.py crop-model SAU        Saudi Arabia: ml/outputs/farming_SAU.json (the first run downloads its NASA
                                        POWER grid once, no login; then a few minutes)

The model needs no farm data to answer: it reads the climate of each grid cell (six NASA POWER measurements)
and says how well that climate fits each crop. Crop maps (IFPRI MapSPAM) were used only to TRAIN it, and here only
to say which cells are farmed today (the "Farmed today" line in the app).

The model (ml/crop_model/, "crop-suitability-v3.1") is Manus's v2 model (trained with Manus in a Kaggle-style
notebook) retrained here to remove rain-only false alarms (ml/crop_model/retrain/): one XGBoost classifier per crop, 40 crops, learned from where each crop is grown
today (IFPRI MapSPAM 2020, 22,450 farmland cells worldwide) described by 10 climate features computed
from six NASA POWER measurements (T2M, T2M_MAX, PRECTOTCORR, RH2M, GWETTOP, GWETROOT). It runs here
with numpy only (ml/crop_model/crop_engine_v3.py, do not edit: retrain/train_v3.py writes the model it reads).
Model card: ml/model_card.md. Numbers behind it: ml/crop_model/metrics.json.

This script is the bridge to the app. For every grid cell of the Egypt table in the repo it:
1. builds the yearly climate features 2001 to 2025 with the engine's own code;
2. scores the 40 crops, irrigated and rain only, on every feature's trend value for 2025 ("now") and its own
   Theil-Sen trend continued to 2030 and 2035 ("if current trends continue"). All six NASA measurements are
   projected. Rain, humidity and soil wetness first lose the one-time 2015 step of the NASA POWER record
   (decision D5 update, Sat 14 Nov, chosen by Mada: over Egypt POWER rain jumps 2.6 times in 2015 while NASA's
   GPCP rain record changes 1.24 times, see ml/nasa_check.py), so their trend is measured without the jump and
   continued from today's level;
3. gives 2035 a 95% range from the engine's 200 block-bootstrap resamples of the years;
4. adds the warming trend and its evidence level from OUR trend engine (decision D1 + FDR, the same
   numbers as the Trends tab), the same for NASA's station record (GISTEMP 250 km), the farmland that
   exists today (MapSPAM) and a flag for climates the model never saw in training;
5. writes the file the Crops, Farmland and Decisions tabs read (contracts/farming.schema.json).

v2 (Manus) was checked against the training run: the scores equalled the notebook's own Egypt export for all 341 land cells, 40 crops, both water modes and all three years (largest difference 0). v3 uses the same code path.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "ml" / "crop_model"
MODEL_FILE = MODEL_DIR / "crop_suitability_v3.npz"
TRAINING_TABLE = MODEL_DIR / "training" / "cropshift_v2_training_cells.parquet"
OUT = ROOT / "ml" / "outputs" / "farming_EGY.json"
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(MODEL_DIR))

import crop_engine_v3 as ce  # noqa: E402  (the trained model's runtime, numpy only)
import farming as fao        # noqa: E402  (grid, border and file helpers shared with the FAO calculator)
import borders               # noqa: E402  (country borders, any ISO code)
import live                  # noqa: E402  (NASA POWER grid for any box, downloaded once and kept on disk)
import nasa_check            # noqa: E402  (NASA GISTEMP station warming per cell)
import trends as T           # noqa: E402  (decision D1 trend engine)

VERSION = "0.6"
BASE_YEAR = 2025
HORIZONS = (5, 10)                 # years after BASE_YEAR
N_BOOT, BLOCK_LEN, SEED = 200, 3, 42   # the training run's settings: keep them, or the numbers change
FARMLAND_MIN_HA = 1000             # same rule as the model's training farmland
SUITABLE = 50
MODES = ("irrigated", "rainfed")
# Focus countries for the farming tabs (decision D7). Egypt reads the repo's NASA table; the others are fetched
# from NASA POWER for the box around the border (data/cache/, downloaded once). The API serves the same list.
COUNTRIES = {"EGY": "Egypt", "SAU": "Saudi Arabia"}
# Decision D5 update: every feature follows its trend. The moisture features (POWER rain and what responds to it)
# have the 2015 step of the record taken out before their trend is measured.
TEMPERATURE = ("t_mean", "t_coldest", "t_warmest", "tmax_hottest")
STEP_FEATURES = tuple(f for f in ce.FEATURES if f not in TEMPERATURE)
STEP_YEAR = 2015                   # before = up to 2014, after = from 2016 (same split as ml/nasa_check.py)
EVIDENCE = {2: "S", 1: "M", 0: "N", -1: "-"}
IFPRI_NOTICE = ("This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no "
                "responsibility for the analyses or interpretations of the data presented here.")
METHOD = ("Machine-learned crop suitability (model crop-suitability-v3.1): one XGBoost model per crop, trained on where "
          "40 crops are grown today (IFPRI MapSPAM 2020, 22,450 farmland cells worldwide), each cell described by "
          "10 climate features from six NASA POWER measurements, 2001 to 2025. On regions held out of training it "
          "tells places that grow a crop from places that do not with AUC 0.90. Rain only also needs enough rain: scores fade to 0 below 100 mm a year (200 mm is full strength for wheat and barley, 250 mm for other crops). "
          "Now and future years: each of the 10 climate features follows its own 2001 to 2025 trend (Theil-Sen), continued to "
          "2030 and 2035, with a 95% range from 200 resamples of the years. For rain, humidity and soil wetness the one-time "
          "2015 step of the NASA POWER record is taken out before the trend is measured (NASA's GPCP rain record does not "
          "show it over Egypt and Saudi Arabia), and the trend continues from today's level. Not a forecast.")
SOURCE = "NASA POWER climate and a model trained on IFPRI MapSPAM 2020 crop maps"
SCORE_NOTE = ("A score runs from 0 to 100: how typical this climate is of the places where the crop is grown today. "
              "50 means as typical of places that grow it as of places that do not. It is not a yield and not the "
              "chance of a good harvest. Irrigated assumes water can be supplied; it does not show that water exists "
              "here. The NASA POWER rain record jumps around 2015 over Egypt and Saudi Arabia; that step is not carried into the "
              "future, only the trend measured without it. Crops grown only on small areas can score low even where they are "
              "grown. Olive and date palm are not separate crops in the crop maps (date palm is counted under tropical fruit). "
              + IFPRI_NOTICE)


def out_path(iso: str) -> Path:
    return ROOT / "ml" / "outputs" / f"farming_{iso}.json"


def country_geometry(iso: str) -> dict:
    """Egypt: the detailed border the app draws; other countries: Natural Earth 1:50m (ml/borders.py)."""
    if iso == "EGY":
        return json.loads(fao.BORDER.read_text(encoding="utf-8"))["geometry"]
    return borders.country(iso)[1]


def _bbox(geometry: dict) -> tuple[float, float, float, float]:
    """lat_min, lat_max, lon_min, lon_max of a Polygon or MultiPolygon, widened by one grid cell."""
    polys = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    pts = np.array([pt for poly in polys for ring in poly for pt in ring], dtype=float)
    dlat, dlon = fao.GRID_STEP
    return (float(pts[:, 1].min() - dlat), float(pts[:, 1].max() + dlat),
            float(pts[:, 0].min() - dlon), float(pts[:, 0].max() + dlon))


def country_cubes(iso: str, geometry: dict) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """lats, lons and {measurement: monthly values [lat, lon, year, 12]} for the six NASA POWER measurements."""
    if iso == "EGY":                                  # the repo's table, so Egypt's numbers stay exactly as before
        lats, lons, cube_t = fao.monthly_cube("T2M")
        return lats, lons, {"T2M": cube_t} | {v: fao.monthly_cube(v)[2] for v in ce.POWER_PARAMS if v != "T2M"}
    box = _bbox(geometry)
    cubes, lats, lons = {}, None, None
    for v in ce.POWER_PARAMS:
        d = live.world_src.region_monthly(v, *box)   # downloads missing 10 x 10 degree tiles once, then from disk
        lats, lons = np.asarray(d["lats"], float), np.asarray(d["lons"], float)
        vals = np.asarray(d["values"], float)
        cubes[v] = vals.reshape(*vals.shape[:2], -1, 12)[:, :, :fao.END - fao.START + 1]
    return lats, lons, cubes


def load_engine() -> "ce.CropSuitabilityEngine":
    return ce.CropSuitabilityEngine.load(MODEL_FILE)


def crop_id(name: str) -> str:
    return name.lower().replace(" ", "_")


def cell_parameters(cubes: dict[str, np.ndarray], i: int, j: int) -> dict[str, dict[str, float]]:
    """One cell's monthly values in the shape the engine reads: {'T2M': {'YYYYMM': value}, ...}."""
    out: dict[str, dict[str, float]] = {}
    for var, cube in cubes.items():
        vals = cube[i, j]
        out[var] = {f"{fao.START + y}{m + 1:02d}": float(vals[y, m])
                    for y in range(vals.shape[0]) for m in range(12) if np.isfinite(vals[y, m])}
    return out


def remove_step(prep: dict) -> dict:
    """Decision D5 update: the moisture features are projected with their trend measured WITHOUT the 2015 step.

    Per feature: step = median(2016 to 2025) - median(2001 to 2014); the years after 2015 are lowered by it, the
    Theil-Sen trend and its block bootstrap (same resamples as the engine) are measured on that series, and the step
    is added back, so the projection starts from today's level and only the trend is free of the jump.
    Temperature features keep the engine's values. Edits prep in place; prep["step"] keeps each feature's step."""
    years = prep["years"]
    before, after = years < STEP_YEAR, years > STEP_YEAR
    cols = [ce.FEATURES.index(f) for f in STEP_FEATURES]
    Y = prep["Fy"][:, cols].T.copy()                                   # (features, years)
    step = np.median(Y[:, after], axis=1) - np.median(Y[:, before], axis=1) if before.any() and after.any()         else np.zeros(len(cols))
    Y[:, after] -= step[:, None]
    idx = ce.block_bootstrap_indices(len(years), prep["n_boot"], BLOCK_LEN, SEED)
    proj = ce.project_series(Y, years, prep["base_year"], prep["H"], idx)
    pt, dr = prep["pt"].copy(), prep["dr"].copy()
    pt[:, cols] = (proj["point"] + step[:, None]).T                   # (H, features)
    dr[:, :, cols] = np.transpose(proj["draws"] + step[:, None, None], (1, 2, 0))
    prep["pt"], prep["dr"] = ce.clip_features(pt), ce.clip_features(dr)
    prep["step"] = dict(zip(STEP_FEATURES, step.tolist()))
    return prep


def prepare_cells(cubes: dict[str, np.ndarray], inside: np.ndarray) -> dict[int, dict]:
    """Yearly features, trend values and bootstrap draws for every cell inside the country that has
    all six measurements (sea cells have no soil wetness and are skipped)."""
    ncols = inside.shape[1]
    preps: dict[int, dict] = {}
    for i, j in zip(*np.nonzero(inside)):
        try:
            preps[int(i) * ncols + int(j)] = remove_step(ce._prepare(cell_parameters(cubes, i, j), BASE_YEAR,
                                                                     HORIZONS, N_BOOT, BLOCK_LEN, SEED))
        except ValueError:
            continue
    return preps


def score_cells(engine, preps: dict[int, dict]) -> dict[str, dict[int, tuple[np.ndarray, np.ndarray]]]:
    """mode -> cell -> (scores at now / +5 / +10 [3, crops], scores of the +10 draws [N_BOOT, crops])."""
    keys = list(preps)
    n_h = len(HORIZONS) + 1
    rows = np.vstack([np.vstack([preps[k]["pt"], preps[k]["dr"][:, -1, :]]) for k in keys])
    per_cell = n_h + N_BOOT
    out: dict[str, dict[int, tuple[np.ndarray, np.ndarray]]] = {}
    for mode in MODES:
        t0 = time.time()
        s = engine.suitability(rows, mode)
        out[mode] = {k: (s[n * per_cell:n * per_cell + n_h], s[n * per_cell + n_h:(n + 1) * per_cell])
                     for n, k in enumerate(keys)}
        print(f"  scored {len(rows):,} climates, {mode}: {time.time() - t0:.0f} s")
    return out


def warming(cube_t: np.ndarray, inside: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Warming trend per decade and its evidence level (decision D1, FDR over the country's cells)."""
    annual = T.annual_means(cube_t.reshape(*cube_t.shape[:2], -1))
    res = T.trend_grid(annual)
    p = np.where(inside, res["p"], np.nan)
    return res["slope"], T.confidence_levels(T.fdr_bh(p))


def farmland_today(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """True where MapSPAM 2020 has at least 1,000 ha harvested in the cell (the model's own farmland rule)."""
    df = pd.read_parquet(TRAINING_TABLE, columns=["lat", "lon", "TA_total"])
    df = df[df["TA_total"] >= FARMLAND_MIN_HA]
    farmed = {(round(float(a), 3), round(float(b), 3)) for a, b in zip(df["lat"], df["lon"])}
    return np.array([[(round(float(la), 3), round(float(lo), 3)) in farmed for lo in lons] for la in lats])


def _grid(n: int, values: dict[int, float], digits: int | None = None) -> list:
    out: list = [None] * n
    for k, v in values.items():
        if np.isfinite(v):
            out[k] = int(round(float(v))) if digits is None else round(float(v), digits)
    return out


def _bits(mask: np.ndarray) -> str:
    return "".join("1" if v else "0" for v in mask.ravel())


def build(iso: str = "EGY") -> dict:
    if iso not in COUNTRIES:
        raise SystemExit(f"Unknown focus country {iso}. Choose one of: {', '.join(COUNTRIES)} (add it to COUNTRIES first).")
    country_name = COUNTRIES[iso]
    engine = load_engine()
    border = country_geometry(iso)
    lats, lons, cubes = country_cubes(iso, border)
    cube_t = cubes["T2M"]
    polys = [border["coordinates"]] if border["type"] == "Polygon" else border["coordinates"]
    touches = np.array([[fao.touches_country(float(la), float(lo), polys) for lo in lons] for la in lats])

    preps = prepare_cells(cubes, touches)
    print(f"{len(preps)} cells inside {country_name} with all six NASA measurements; scoring {engine.n_crops} crops")
    scores = score_cells(engine, preps)
    n = touches.size
    inside = np.zeros(n, dtype=bool)
    inside[list(preps)] = True          # a cell with no land data is not drawn at all

    suit, low, high = {}, {}, {}
    for mode in MODES:
        suit[mode], low[mode], high[mode] = {}, {}, {}
        for c, name in enumerate(engine.crops):
            cid = crop_id(name)
            point = {k: 100 * scores[mode][k][0][:, c] for k in preps}
            draws = {k: 100 * scores[mode][k][1][:, c] for k in preps}
            suit[mode][cid] = [_grid(n, {k: v[h] for k, v in point.items()}) for h in range(len(HORIZONS) + 1)]
            last = suit[mode][cid][-1]
            lo = _grid(n, {k: np.percentile(d, 2.5) for k, d in draws.items()})
            hi = _grid(n, {k: np.percentile(d, 97.5) for k, d in draws.items()})
            low[mode][cid] = [None if v is None else min(v, last[k]) for k, v in enumerate(lo)]
            high[mode][cid] = [None if v is None else max(v, last[k]) for k, v in enumerate(hi)]

    slope, level = warming(cube_t, inside.reshape(touches.shape))
    st_slope, st_level, _ = nasa_check.station_warming(lats, lons)
    outside_training = {k: not bool(engine.in_training_range(p["pt"]).all()) for k, p in preps.items()}
    dlat, dlon = fao.GRID_STEP
    return {
        "version": VERSION,
        "region": {"id": iso, "name": country_name, "bbox": [float(lons[0] - dlon / 2), float(lats[0] - dlat / 2),
                                                          float(lons[-1] + dlon / 2), float(lats[-1] + dlat / 2)]},
        "grid": {"lat0": float(lats[0]), "lon0": float(lons[0]), "dlat": dlat, "dlon": dlon,
                 "nrows": len(lats), "ncols": len(lons)},
        "method": METHOD,
        "source": SOURCE,
        "score_note": SCORE_NOTE,
        "model": {"id": engine.version, "algorithm": engine.meta.get("algorithm"), "trained_utc": engine.meta.get("trained_utc")},
        "climate_period": f"trend value for {BASE_YEAR}",
        "horizons": [BASE_YEAR] + [BASE_YEAR + h for h in HORIZONS],
        "suitable_threshold": SUITABLE,
        "inside": _bits(inside),
        "farmland": _bits(farmland_today(lats, lons).ravel() & inside),
        "outside_training": _bits(np.array([outside_training.get(k, False) for k in range(n)])),
        "evidence": "".join(EVIDENCE[int(v)] if inside[k] else "-" for k, v in enumerate(level.ravel())),
        "temp_trend_per_decade": _grid(n, {k: slope.ravel()[k] for k in preps}, 3),
        "station_evidence": "".join(EVIDENCE[int(v)] if inside[k] else "-" for k, v in enumerate(st_level.ravel())),
        "station_trend_per_decade": _grid(n, {k: st_slope.ravel()[k] for k in preps}, 3),
        "temp_now_c": _grid(n, {k: p["pt"][0, ce.FEATURES.index("t_mean")] for k, p in preps.items()}, 1),
        "rain_now_mm": _grid(n, {k: p["pt"][0, ce.FEATURES.index("rain_annual")] for k, p in preps.items()}, 0),
        "crops": [{"id": crop_id(name), "name": name[0].upper() + name[1:]} for name in engine.crops],
        "suitability": suit,             # [mode][crop] -> [2025, 2030, 2035], each a flat grid of 0 to 100 or null
        "suitability_10_low": low,       # 2035, low end of the 95% range
        "suitability_10_high": high,
    }


def report(o: dict) -> None:
    """A few lines a human can check against common sense."""
    cells = [k for k, c in enumerate(o["inside"]) if c == "1"]
    ids = [c["id"] for c in o["crops"]]

    def fits(mode: str, h: int, k: int) -> int:
        return sum((o["suitability"][mode][c][h][k] or 0) >= SUITABLE for c in ids)

    dry = [k for k in cells if (o["rain_now_mm"][k] or 0) < 50]
    farm = [k for k in cells if o["farmland"][k] == "1"]
    print(f"{len(cells)} cells, {len(farm)} with farmland today, {o['outside_training'].count('1')} outside the training climates")
    print(f"dry cells (under 50 mm rain, {len(dry)}): crops that fit on rain only {np.mean([fits('rainfed', 0, k) for k in dry]):.2f}, "
          f"irrigated {np.mean([fits('irrigated', 0, k) for k in dry]):.1f} (of {len(ids)})")
    print(f"farmland today: crops that fit irrigated {np.mean([fits('irrigated', 0, k) for k in farm]):.1f} now, "
          f"{np.mean([fits('irrigated', 2, k) for k in farm]):.1f} in {o['horizons'][-1]}")
    print("evidence of warming:", {name: o["evidence"].count(letter) for letter, name in
                                   (("S", "strong"), ("M", "moderate"), ("N", "not proven"))})
    print("evidence of warming, NASA station record:", {name: o["station_evidence"].count(letter) for letter, name in
                                   (("S", "strong"), ("M", "moderate"), ("N", "not proven"))})


if __name__ == "__main__":
    t0 = time.time()
    iso = (sys.argv[1] if len(sys.argv) > 1 else "EGY").upper()
    outlook = build(iso)
    out = out_path(iso)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(outlook, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    report(outlook)
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB) in {time.time() - t0:.0f} s. Check it: python run.py farming-check {out}")
