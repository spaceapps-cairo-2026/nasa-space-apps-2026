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


def region_fixture(code: str = "T2M") -> tuple[dict, dict]:
    df = pd.read_parquet(GRID)
    df = df[df["variable"] == code].copy()
    df["year"] = df["time"].str[:4].astype(int)
    dlat, dlon = EGYPT_CELL
    cells, ps = [], []
    for (cid, lat, lon), g in df.groupby(["cell_id", "lat", "lon"]):
        monthly = {y: gg["value"].dropna().tolist() for y, gg in g.groupby("year")}
        t = trend_of(annual_means(monthly, code))
        cells.append({
            "id": cid, "lat": lat, "lon": lon,
            "bounds": [lon - dlon / 2, lat - dlat / 2, lon + dlon / 2, lat + dlat / 2],
            "slope_per_decade": t["slope_per_decade"], "p": t["p"], "q": None,
            "confidence": "not_proven", "direction": "no_clear_trend", "change_start_year": None,
        })
        ps.append(t["p"])
    q = multipletests(ps, method="fdr_bh")[1]
    for c, qq in zip(cells, q):
        c["q"] = round(float(qq), 6)
        c["confidence"] = confidence(c["q"])
        if c["confidence"] != "not_proven":
            c["direction"] = "increasing" if c["slope_per_decade"] > 0 else "decreasing"
    lats, lons = df["lat"].unique(), df["lon"].unique()
    region = {
        "id": "egypt", "name": "Egypt (grid box 22 to 32 N, 25 to 35 E)",
        "bbox": [float(lons.min() - dlon / 2), float(lats.min() - dlat / 2), float(lons.max() + dlon / 2), float(lats.max() + dlat / 2)],
        "n_cells": len(cells), "grid": "0.5 x 0.625 degrees (NASA POWER / MERRA-2)",
    }
    slopes = [c["slope_per_decade"] for c in cells]
    summary = {
        "n_cells": len(cells),
        "n_increasing": sum(c["direction"] == "increasing" for c in cells),
        "n_decreasing": sum(c["direction"] == "decreasing" for c in cells),
        "n_not_proven": sum(c["confidence"] == "not_proven" for c in cells),
        "median_slope_per_decade": round(float(np.median(slopes)), 4),
    }
    trend = {"version": VERSION, "region": region, "variable": VAR[code], "period": {"start": START, "end": END},
             "method": METHOD, "cells": cells, "summary": summary}
    return trend, region


def write(name: str, obj: dict) -> None:
    (FIX / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", FIX / name)


if __name__ == "__main__":
    write("variables.json", {"version": VERSION, "variables": VARIABLES})
    reg_trend, region = region_fixture("T2M")
    write("regions.json", {"version": VERSION, "regions": [region]})
    write("trend_region_egypt_T2M.json", reg_trend)
    pt = point_fixture()
    write("trend_point_cairo_T2M.json", pt)
    print("Cairo:", pt["sentence"])
    print("Egypt T2M summary:", reg_trend["summary"])
