"""Lane A: build the v0.3 F1 fixtures in contracts/fixtures/ from the real NASA POWER download.

The numbers come from real data, but the method is a PLACEHOLDER until decision D1:
annual means, Mann-Kendall with Hamed-Rao autocorrelation correction, Sen's slope with a
95% interval, Benjamini-Hochberg FDR across the region. Change start year is left null.

Run:  python ml/make_trend_fixtures.py   (needs `python run.py power` first)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "contracts" / "fixtures"
GRID = ROOT / "data" / "processed" / "power_monthly.parquet"
CAIRO = ROOT / "data" / "cache" / "power_points" / "cairo_30.04_31.24.json"
VERSION = "0.3"
START, END = 2001, 2025
METHOD = "PLACEHOLDER until D1: annual means, Mann-Kendall (Hamed-Rao correction), Sen's slope, BH-FDR on maps"
SOURCE = "NASA POWER monthly (MERRA-2 based)"
PRECIP_CAUTION = "Over very dry desert, rainfall is close to zero in most years, so trends there are unreliable."

VARIABLES = [
    {"code": "T2M", "name": "Air temperature", "unit": "°C", "source": SOURCE,
     "definition": "Average temperature of the air 2 meters above the ground.", "point": True, "regions": ["egypt"], "caution": None},
    {"code": "T2M_MAX", "name": "Daily maximum temperature", "unit": "°C", "source": SOURCE,
     "definition": "The hottest temperature of each day, averaged over the year.", "point": True, "regions": ["egypt"], "caution": None},
    {"code": "T2M_MIN", "name": "Daily minimum temperature", "unit": "°C", "source": SOURCE,
     "definition": "The coldest temperature of each day (usually at night), averaged over the year.", "point": True, "regions": [], "caution": None},
    {"code": "PRECTOTCORR", "name": "Rainfall", "unit": "mm per year", "source": SOURCE,
     "definition": "Total rain and snow that falls in a year, as a depth of water in millimeters.", "point": True, "regions": ["egypt"], "caution": PRECIP_CAUTION},
    {"code": "GWETTOP", "name": "Topsoil wetness", "unit": "0 to 1", "source": SOURCE,
     "definition": "How wet the top 5 cm of soil is: 0 is completely dry, 1 is fully soaked.", "point": False, "regions": ["egypt"], "caution": None},
    {"code": "GWETROOT", "name": "Root zone wetness", "unit": "0 to 1", "source": SOURCE,
     "definition": "How wet the soil is down to about 1 meter, where plant roots drink: 0 is dry, 1 is soaked.", "point": True, "regions": ["egypt"], "caution": None},
    {"code": "RH2M", "name": "Relative humidity", "unit": "%", "source": SOURCE,
     "definition": "How much water vapor the air holds, compared with the most it could hold at that temperature.", "point": True, "regions": ["egypt"], "caution": None},
]
VAR = {v["code"]: v for v in VARIABLES}
EGYPT_CELL = (0.5, 0.625)  # grid spacing in degrees (lat, lon)


def annual_means(monthly: dict[int, list[float]], code: str) -> list[dict]:
    """monthly: year -> list of valid monthly values. A year needs 9+ valid months."""
    out = []
    for y in range(START, END + 1):
        vals = monthly.get(y, [])
        v = float(np.mean(vals)) if len(vals) >= 9 else None
        if v is not None and code == "PRECTOTCORR":
            v *= 365.25  # mm/day averaged over the year -> mm per year
        out.append({"year": y, "value": None if v is None else round(v, 4), "n_months": len(vals)})
    return out


def sen_interval(x: np.ndarray, var_s: float, alpha: float = 0.05) -> tuple[float, float]:
    """95% interval for Sen's slope from the ranked pairwise slopes (Gilbert 1987)."""
    n = len(x)
    slopes = np.sort([(x[j] - x[i]) / (j - i) for i in range(n) for j in range(i + 1, n)])
    c = norm.ppf(1 - alpha / 2) * np.sqrt(var_s)
    m1 = int(np.floor((len(slopes) - c) / 2))
    m2 = int(np.ceil((len(slopes) + c) / 2))
    return float(slopes[max(m1, 0)]), float(slopes[min(m2, len(slopes) - 1)])


def confidence(p_or_q: float) -> str:
    return "strong" if p_or_q < 0.01 else "moderate" if p_or_q < 0.05 else "not_proven"


def trend_of(series: list[dict]) -> dict:
    pts = [(s["year"], s["value"]) for s in series if s["value"] is not None]
    years = np.array([p[0] for p in pts])
    x = np.array([p[1] for p in pts])
    r = mk.hamed_rao_modification_test(x)
    lo, hi = sen_interval(x, mk.original_test(x).var_s)
    slope = float(r.slope)
    mid_year, mid_val = float(np.median(years)), float(np.median(x))
    line = [{"year": int(y), "value": round(mid_val + slope * (y - mid_year), 4)} for y in (years[0], years[-1])]
    conf = confidence(float(r.p))
    return {
        "slope_per_decade": round(slope * 10, 4), "ci_low": round(lo * 10, 4), "ci_high": round(hi * 10, 4),
        "p": round(float(r.p), 6), "q": None, "confidence": conf,
        "direction": "no_clear_trend" if conf == "not_proven" else ("increasing" if slope > 0 else "decreasing"),
        "method": METHOD, "change_start_year": None, "line": line,
    }


def sentence(var: dict, place: str, t: dict) -> str:
    rate = f"{t['slope_per_decade']:+.2f} {var['unit']} per decade"
    what = var["name"].lower()
    if t["confidence"] == "not_proven":
        return (f"Since {START}, {what} {place} changed by {rate}, but this could be normal "
                f"year to year variation (not proven).")
    verb = "rose" if t["slope_per_decade"] > 0 else "fell"
    ev = "Strong evidence" if t["confidence"] == "strong" else "Moderate evidence"
    return f"Since {START}, {what} {place} {verb} by {rate}. {ev} this is a real change."


def point_fixture() -> dict:
    raw = json.loads(CAIRO.read_text())
    params = raw["properties"]["parameter"]["T2M"]
    monthly: dict[int, list[float]] = {}
    for key, v in params.items():
        y, m = int(key[:4]), int(key[4:])
        if 1 <= m <= 12 and v != -999:
            monthly.setdefault(y, []).append(v)
    series = annual_means(monthly, "T2M")
    t = trend_of(series)
    return {
        "version": VERSION, "variable": VAR["T2M"],
        "location": {"lat": 30.04, "lon": 31.24, "name": "Cairo", "cell": None, "region": None},
        "period": {"start": START, "end": END}, "series": series, "trend": t,
        "sentence": sentence(VAR["T2M"], "in Cairo", t), "caution": None, "cached": True,
    }


GRID_STEP = (0.5, 0.625)  # NASA POWER grid (lat, lon)
GRID_METHOD = ("PLACEHOLDER until D1: annual means, straight-line trend with a t-test per cell "
               "(vectorized, fast enough for the whole world), Benjamini-Hochberg FDR over the cells of the map")
WORLD = ROOT / "data" / "processed" / "world"


def grid_trend(lats: np.ndarray, lons: np.ndarray, ann: np.ndarray, region: dict, code: str) -> dict:
    """ann: [n_lat, n_lon, n_years] yearly means (NaN = missing) -> GridTrend (contracts/api.md)."""
    from scipy import stats
    x = np.arange(START, END + 1, dtype=float)
    x -= x.mean()
    valid = np.isfinite(ann)
    n = valid.sum(-1)
    nz = np.maximum(n, 1)
    xm = np.where(valid, x, 0).sum(-1) / nz
    ym = np.where(valid, ann, 0).sum(-1) / nz
    dx = np.where(valid, x - xm[..., None], 0.0)
    dy = np.where(valid, ann - ym[..., None], 0.0)
    sxx = (dx * dx).sum(-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        b = (dx * dy).sum(-1) / sxx
        resid = np.where(valid, dy - b[..., None] * dx, 0.0)
        se = np.sqrt((resid ** 2).sum(-1) / np.maximum(n - 2, 1) / sxx)
        p = 2 * stats.t.sf(np.abs(b / se), np.maximum(n - 2, 1))
    ok = (n >= 15) & np.isfinite(p) & np.isfinite(b)
    q = np.full(p.shape, np.nan)
    q[ok] = multipletests(p[ok], method="fdr_bh")[1]
    conf = np.full(p.shape, "-", dtype="<U1")
    conf[ok] = np.where(q[ok] < 0.01, "S", np.where(q[ok] < 0.05, "M", "N"))
    slope = np.where(ok, b * 10, np.nan)
    flat = lambda a, d: [None if not np.isfinite(v) else round(float(v), d) for v in a.ravel()]
    proven = ok & (conf != "N")
    dlat, dlon = GRID_STEP
    return {
        "version": VERSION, "region": {**region, "n_cells": int(ok.sum()), "grid": "0.5 x 0.625 degrees (NASA POWER / MERRA-2)"},
        "variable": VAR[code], "period": {"start": START, "end": END}, "method": GRID_METHOD,
        "grid": {"lat0": float(lats[0]), "lon0": float(lons[0]), "dlat": dlat, "dlon": dlon, "nrows": len(lats), "ncols": len(lons)},
        "slope_per_decade": flat(slope, 3), "q": flat(q, 4), "confidence": "".join(conf.ravel()),
        "summary": {
            "n_cells": int(ok.sum()), "n_increasing": int((proven & (slope > 0)).sum()),
            "n_decreasing": int((proven & (slope < 0)).sum()), "n_not_proven": int((ok & (conf == "N")).sum()),
            "median_slope_per_decade": round(float(np.nanmedian(slope)), 4),
        },
    }


def egypt_annual(code: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    df = pd.read_parquet(GRID)
    df = df[df["variable"] == code].copy()
    df["year"] = df["time"].str[:4].astype(int)
    g = df.groupby(["lat", "lon", "year"])["value"]
    ann = g.mean().where(g.count() >= 9).unstack("year").reindex(columns=range(START, END + 1))
    lats, lons = np.sort(df["lat"].unique()), np.sort(df["lon"].unique())
    cube = np.full((len(lats), len(lons), END - START + 1), np.nan)
    li, lj = {v: i for i, v in enumerate(lats)}, {v: j for j, v in enumerate(lons)}
    for (lat, lon), row in ann.iterrows():
        cube[li[lat], lj[lon], :] = row.to_numpy()
    return lats, lons, cube


def region_fixture(code: str = "T2M") -> tuple[dict, dict]:
    lats, lons, cube = egypt_annual(code)
    dlat, dlon = GRID_STEP
    region = {"id": "egypt", "name": "Egypt",
              "bbox": [float(lons[0] - dlon / 2), float(lats[0] - dlat / 2), float(lons[-1] + dlon / 2), float(lats[-1] + dlat / 2)]}
    return grid_trend(lats, lons, cube, region, code), region


def world_fixture(code: str = "T2M") -> dict:
    with np.load(WORLD / f"{code}_annual.npz") as z:
        lats, lons, vals, years = z["lats"], z["lons"], z["values"].astype(float), z["years"]
    assert int(years[0]) == START and int(years[-1]) == END
    return grid_trend(lats, lons, vals, {"id": "world", "name": "Whole Earth", "bbox": [-180.3125, -90.25, 179.6875, 90.25]}, code)


def write(name: str, obj: dict) -> None:
    (FIX / name).write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print("wrote", FIX / name)


if __name__ == "__main__":
    write("variables.json", {"version": VERSION, "variables": VARIABLES})
    reg_trend, region = region_fixture("T2M")
    write("regions.json", {"version": VERSION, "regions": [region]})
    write("trend_region_egypt_T2M.json", reg_trend)
    world = world_fixture("T2M")
    (FIX / "trend_world_T2M.json").write_text(json.dumps(world, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print("wrote world fixture, summary:", world["summary"])
    pt = point_fixture()
    write("trend_point_cairo_T2M.json", pt)
    print("Cairo:", pt["sentence"])
    print("Egypt T2M summary:", reg_trend["summary"])
