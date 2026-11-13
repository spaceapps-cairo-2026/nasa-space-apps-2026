"""Farming outlook for a focus country (F2 farmland, F3 crops, F4 decisions). Egypt first.

Built by lane B (Eyad + Claude) at the team's request because lane A is on the trend engine;
lane A please review. Output shape: contracts/api.md "FarmingOutlook".

Method (FAO ECOCROP crop suitability, the same idea as Hijmans' EcoCrop model):
1. Climate now. For every NASA POWER grid cell: the average of each calendar month over the last
   10 years (2016 to 2025) for air temperature (T2M) and rainfall (PRECTOTCORR).
2. Climate later, "if current trends continue": the cell's own measured trend (straight line over
   2001 to 2025 of the yearly mean temperature and the yearly rainfall total) is added to every
   month. Horizons: 2025 (now), 2030 (+5), 2035 (+10). A low / high version uses the trend's 95%
   range, so every future number comes with its uncertainty.
3. Crop suitability, 0 to 100, for every crop and every possible growing season:
   - temperature score: each month scored on its own, 100 inside the crop's OPTIMAL range,
     falling linearly to 0 at its ABSOLUTE limits; one month outside the absolute limits = 0
     (the crop dies); otherwise the average of the months
   - trees (perennials) must survive all 12 months; seasonal crops get FAO's shortest cycle
   - rain score (rain-fed mode only): rain total of the season against the crop's rain ranges;
     irrigated mode ignores rain (water comes from the Nile or wells)
   - season score = the lower of the two; crop score = the best season of the year
4. Farmland viability of a cell = its best crop score; "crops that fit" = crops scoring 50 or more.
5. Evidence: each cell carries the confidence of its temperature trend (S strong, M moderate,
   N not proven, as in the trend maps). Future changes in cells marked N rest on a trend that is
   not proven and the app says so.

Run:  python ml/farming.py      writes ml/outputs/farming_EGY.json and contracts/fixtures/farming_EGY.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data" / "processed" / "power_monthly.parquet"
CROPS = ROOT / "data" / "crops" / "crops.csv"
BORDER = ROOT / "app" / "data" / "regions" / "EGY.geojson"
OUTS = [ROOT / "ml" / "outputs" / "farming_EGY.json", ROOT / "contracts" / "fixtures" / "farming_EGY.json"]

VERSION = "0.4"
START, END = 2001, 2025
BASE_START, BASE_END = 2016, 2025          # "climate now" = last 10 years
BASE_CENTER = (BASE_START + BASE_END) / 2  # 2020.5
HORIZONS = [2025, 2030, 2035]
DAYS = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
GRID_STEP = (0.5, 0.625)
SUITABLE = 50  # a crop "fits" a place when it scores at least this
METHOD = ("FAO ECOCROP suitability on NASA POWER monthly climate (2016 to 2025 average), best growing season of "
          "the year; future = each cell's own 2001 to 2025 trend continued, with its 95% range. Not a forecast.")
SOURCE = "NASA POWER climate and FAO ECOCROP crop needs"
SCORE_NOTE = ("Scores follow FAO ECOCROP: 100 when every month of the growing season is inside the crop's ideal "
              "temperature range, 0 if any month is outside what the crop can survive. \"Heat limit\" = years until "
              "the hottest month of the season reaches that survival limit, if this place keeps warming at its "
              "measured rate.")


# ---------- climate ----------

def monthly_cube(var: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """-> lats, lons, values[n_lat, n_lon, n_years, 12] (NaN = missing)."""
    df = pd.read_parquet(GRID)
    df = df[df["variable"] == var].copy()
    df["year"] = df["time"].str[:4].astype(int)
    df["month"] = df["time"].str[5:7].astype(int)
    lats, lons = np.sort(df["lat"].unique()), np.sort(df["lon"].unique())
    li = {v: i for i, v in enumerate(lats)}
    lj = {v: j for j, v in enumerate(lons)}
    cube = np.full((len(lats), len(lons), END - START + 1, 12), np.nan)
    for lat, lon, y, m, v in df[["lat", "lon", "year", "month", "value"]].itertuples(index=False):
        cube[li[lat], lj[lon], y - START, m - 1] = v
    return lats, lons, cube


def yearly_trend(yearly: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """yearly[n_lat, n_lon, n_years] -> slope per year, its standard error, p-value (straight line)."""
    x = np.arange(yearly.shape[-1], dtype=float)
    x -= x.mean()
    valid = np.isfinite(yearly)
    n = valid.sum(-1)
    nz = np.maximum(n, 1)
    xm = np.where(valid, x, 0).sum(-1) / nz
    ym = np.where(valid, yearly, 0).sum(-1) / nz
    dx = np.where(valid, x - xm[..., None], 0.0)
    dy = np.where(valid, yearly - ym[..., None], 0.0)
    sxx = (dx * dx).sum(-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        b = (dx * dy).sum(-1) / sxx
        resid = np.where(valid, dy - b[..., None] * dx, 0.0)
        se = np.sqrt((resid ** 2).sum(-1) / np.maximum(n - 2, 1) / sxx)
        p = 2 * stats.t.sf(np.abs(b / se), np.maximum(n - 2, 1))
    return b, se, p


# ---------- ECOCROP ----------

def ramp(x: np.ndarray, amin: float, omin: float, omax: float, amax: float) -> np.ndarray:
    """0 outside [amin, amax], 1 inside [omin, omax], straight lines in between."""
    up = np.clip((x - amin) / max(omin - amin, 1e-9), 0, 1)
    down = np.clip((amax - x) / max(amax - omax, 1e-9), 0, 1)
    return np.where(x < omin, up, np.where(x > omax, down, 1.0))


def season_months(row: pd.Series) -> int:
    """Trees (perennials) must live through all 12 months. Seasonal crops get FAO's SHORTEST
    growing cycle (at least 3 months), the most favourable case for the crop."""
    if str(row.get("life_span", "")).strip() == "perennial":
        return 12
    lo = row["cycle_min_days"]
    if not np.isfinite(lo):
        return 12
    return int(min(12, max(3, round(lo / 30.4))))


def crop_score(temp: np.ndarray, rain_mm: np.ndarray, crop: pd.Series, irrigated: bool) -> tuple[np.ndarray, np.ndarray]:
    """temp, rain_mm: [..., 12] monthly climate -> (score 0 to 100, best start month 0 to 11).

    Every month of the season is scored on its own (100 inside the optimal range, 0 outside the
    absolute range). If ANY month is outside the absolute range the crop dies: season score 0.
    Otherwise the season score is the average of its months. Rain-fed: also limited by the season's
    rain total. The crop's score is its best season of the year.
    """
    L = season_months(crop)
    monthly = ramp(temp, crop["temp_abs_min_c"], crop["temp_opt_min_c"], crop["temp_opt_max_c"], crop["temp_abs_max_c"])
    best = np.zeros(temp.shape[:-1])
    best_m = np.zeros(temp.shape[:-1], dtype=int)
    for start in range(12 if L < 12 else 1):
        idx = [(start + k) % 12 for k in range(L)]
        m = monthly[..., idx]
        s = np.where(m.min(-1) > 0, m.mean(-1), 0.0)
        if not irrigated:
            r = rain_mm[..., idx].sum(-1)
            s = np.minimum(s, ramp(r, crop["rain_abs_min_mm"], crop["rain_opt_min_mm"], crop["rain_opt_max_mm"], crop["rain_abs_max_mm"]))
        better = s > best
        best = np.where(better, s, best)
        best_m = np.where(better, start, best_m)
    return np.round(best * 100), best_m


def heat_margin_years(temp: np.ndarray, crop: pd.Series, start: np.ndarray, trend_per_year: np.ndarray) -> np.ndarray:
    """Years until the hottest month of the crop's best season reaches the crop's absolute heat
    limit, if the cell keeps warming at its current rate. NaN when not warming. Capped at 99."""
    L = season_months(crop)
    hottest = np.full(start.shape, -np.inf)
    for k in range(L):
        month = (start + k) % 12
        hottest = np.maximum(hottest, np.take_along_axis(temp, month[..., None], axis=-1)[..., 0])
    margin = crop["temp_abs_max_c"] - hottest
    with np.errstate(invalid="ignore", divide="ignore"):
        years = np.where(trend_per_year > 0, margin / trend_per_year, np.nan)
    return np.clip(years, 0, 99)


# ---------- border ----------

def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i - 1]
        x2, y2 = ring[i]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def touches_country(lat: float, lon: float, polys: list) -> bool:
    """True if the cell center or one of its corners lies inside the country."""
    dlat, dlon = GRID_STEP
    pts = [(lon, lat)] + [(lon + sx * dlon / 2, lat + sy * dlat / 2) for sx in (-1, 1) for sy in (-1, 1)]
    return any(any(_in_ring(x, y, p[0]) for p in polys) for x, y in pts)


# ---------- main ----------

def flat(a: np.ndarray, digits: int | None = None) -> list:
    if digits is None:
        return [None if not np.isfinite(v) else int(v) for v in a.ravel()]
    return [None if not np.isfinite(v) else round(float(v), digits) for v in a.ravel()]


def build() -> dict:
    lats, lons, T = monthly_cube("T2M")
    _, _, P = monthly_cube("PRECTOTCORR")
    P_mm = P * DAYS                                            # mm/day -> mm per month
    base = slice(BASE_START - START, BASE_END - START + 1)
    t_clim = np.nanmean(T[:, :, base, :], axis=2)              # [lat, lon, 12]
    p_clim = np.nanmean(P_mm[:, :, base, :], axis=2)
    t_year = np.where(np.isfinite(T).sum(-1) >= 9, np.nanmean(T, axis=-1), np.nan)
    p_year = np.where(np.isfinite(P_mm).sum(-1) >= 9, np.nansum(P_mm, axis=-1), np.nan)
    t_b, t_se, t_p = yearly_trend(t_year)
    p_b, _, _ = yearly_trend(p_year)
    ok = np.isfinite(t_p)
    q = np.full(t_p.shape, np.nan)
    q[ok] = multipletests(t_p[ok], method="fdr_bh")[1]
    evidence = np.where(~ok, "-", np.where(q < 0.01, "S", np.where(q < 0.05, "M", "N")))

    border = json.loads(BORDER.read_text(encoding="utf-8"))["geometry"]
    polys = [border["coordinates"]] if border["type"] == "Polygon" else border["coordinates"]
    inside = np.array([[touches_country(float(la), float(lo), polys) for lo in lons] for la in lats])

    p_annual = np.nansum(p_clim, axis=-1)

    def climate(year: float, k: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        dt = year - BASE_CENTER
        t = t_clim + ((t_b + k * 1.96 * t_se) * dt)[..., None]
        with np.errstate(invalid="ignore", divide="ignore"):
            factor = np.clip((p_annual + p_b * dt) / p_annual, 0, None)
        r = p_clim * np.where(np.isfinite(factor), factor, 1.0)[..., None]
        return t, r

    crops = pd.read_csv(CROPS)
    out_crops, suit, best_month, low10, high10, heat_years = [], {}, {}, {}, {}, {}
    for mode in ("irrigated", "rainfed"):
        irr = mode == "irrigated"
        suit[mode], best_month[mode], low10[mode], high10[mode] = {}, {}, {}, {}
        for _, c in crops.iterrows():
            cid = c["crop"].split(" (")[0].replace(" ", "_")
            per_h = []
            for h in HORIZONS:
                s, m = crop_score(*climate(h), c, irr)
                per_h.append(np.where(inside, s, np.nan))
                if h == HORIZONS[0]:
                    best_month[mode][cid] = flat(np.where(inside, m, np.nan))
                    if irr:
                        yrs = heat_margin_years(climate(h)[0], c, m, t_b)
                        heat_years[cid] = flat(np.where(inside & (s > 0), yrs, np.nan))
            suit[mode][cid] = [flat(a) for a in per_h]
            # +10 years with a cooler and a warmer version of the trend (95% range)
            sa, _ = crop_score(*climate(HORIZONS[-1], -1), c, irr)
            sb, _ = crop_score(*climate(HORIZONS[-1], +1), c, irr)
            low10[mode][cid] = flat(np.where(inside, np.minimum(sa, sb), np.nan))
            high10[mode][cid] = flat(np.where(inside, np.maximum(sa, sb), np.nan))
            if mode == "irrigated":
                out_crops.append({"id": cid, "name": c["crop"][0].upper() + c["crop"][1:], "scientific_name": c["scientific_name"],
                                  "season_months": season_months(c), "source_url": c["source_url"],
                                  "temp_opt_c": [float(c["temp_opt_min_c"]), float(c["temp_opt_max_c"])],
                                  "temp_abs_c": [float(c["temp_abs_min_c"]), float(c["temp_abs_max_c"])]})

    dlat, dlon = GRID_STEP
    return {
        "version": VERSION,
        "region": {"id": "EGY", "name": "Egypt", "bbox": [float(lons[0] - dlon / 2), float(lats[0] - dlat / 2),
                                                          float(lons[-1] + dlon / 2), float(lats[-1] + dlat / 2)]},
        "grid": {"lat0": float(lats[0]), "lon0": float(lons[0]), "dlat": dlat, "dlon": dlon, "nrows": len(lats), "ncols": len(lons)},
        "method": METHOD,
        "source": SOURCE,              # shown as "Source: ..." and "from ..." in the app
        "score_note": SCORE_NOTE,      # how to read a score, shown under "How we know" in the cell panel
        "climate_period": f"{BASE_START} to {BASE_END}",
        "horizons": HORIZONS,
        "suitable_threshold": SUITABLE,
        "inside": "".join("1" if v else "0" for v in inside.ravel()),
        "temp_trend_per_decade": flat(t_b * 10, 3),
        "rain_trend_mm_per_decade": flat(p_b * 10, 1),
        "temp_now_c": flat(np.nanmean(t_clim, axis=-1), 1),
        "rain_now_mm": flat(p_annual, 0),
        "evidence": "".join(evidence.ravel()),
        "crops": out_crops,
        "suitability": suit,           # [mode][crop] -> [now, +5, +10], each a flat grid of 0 to 100 or null
        "suitability_10_low": low10,   # +10 with the trend's 95% range
        "suitability_10_high": high10,
        "best_start_month": best_month,  # [mode][crop] -> flat grid, 0 = January
        "years_to_heat_limit": heat_years,  # [crop] -> flat grid (irrigated, now): years until the hottest season month hits the crop's limit at the current warming rate
    }


def is_ours(path: Path) -> bool:
    """True if the file is missing or was written by this calculator (not by a trained model)."""
    if not path.exists():
        return True
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("method") == METHOD
    except (json.JSONDecodeError, OSError):
        return False


if __name__ == "__main__":
    import sys
    out = build()
    for path in OUTS:
        # ml/outputs/ is where a trained model puts its answer: never replace that by accident.
        if "outputs" in path.parts and not is_ours(path) and "--force" not in sys.argv:
            print("kept", path, "(written by another model; use --force to replace it with the FAO calculator)")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print("wrote", path, f"{path.stat().st_size / 1024:.0f} KB")
