"""Lane A: live trends. Gets the data (Egypt from the repo, anywhere else from NASA with a disk
cache), runs the trend engine, and returns the JSON shapes defined in contracts/api.md (v0.4).

This is what the API calls:
    point_trend(variable, lat, lon)                               -> "trend_point"
    region_trend(variable, lat_min, lat_max, lon_min, lon_max, country=None)   -> "trend_region"
    world_trend(variable="T2M", stride=2)                         -> "trend_world"
    variables()                                                   -> the measurement picker

Speed: Egypt and anything fetched before answer in well under a second. A new point waits about
1 to 2 s for NASA; a new region about 5 s per 10 x 10 degree tile.
"""
from __future__ import annotations

import json
import sys
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "ml", ROOT / "data"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import borders  # noqa: E402
import power_point_fetch as point_src  # noqa: E402
import power_world_fetch as world_src  # noqa: E402
import trends as T  # noqa: E402

VERSION = "0.4"
PERIOD = f"{T.START_YEAR}-{T.END_YEAR}"
YEARS = list(range(T.START_YEAR, T.END_YEAR + 1))
SOURCE = "NASA POWER (MERRA-2), monthly, 0.5 x 0.625 degree grid"
EGYPT_BOX = (22.0, 32.0, 25.0, 35.0)             # the grid committed in data/processed/
EGYPT_TABLE = ROOT / "data" / "processed" / "power_monthly.parquet"
WORLD_DIR = ROOT / "data" / "processed" / "world"
OUTPUTS = ROOT / "ml" / "outputs"
MAX_NEW_TILES = 12                               # more missing tiles than this = "zoom in" (about 1 minute)
ARID_MM_DAY = 0.1                                # below this, rain trends get a caution note

# code: (plain name, unit, decimals shown, available for regions)
_VARS = {
    "T2M": ("average air temperature", "C", 2, True),
    "T2M_MAX": ("daily maximum air temperature", "C", 2, True),
    "T2M_MIN": ("daily minimum air temperature", "C", 2, False),
    "PRECTOTCORR": ("precipitation", "mm/day", 3, True),
    "GWETTOP": ("topsoil wetness", "fraction (0 to 1)", 3, True),
    "GWETROOT": ("root zone soil wetness", "fraction (0 to 1)", 3, True),
    "RH2M": ("relative humidity", "%", 2, True),
}
NOT_REACHABLE = ("NASA data is not reachable right now and this place is not saved on this computer yet. "
                 "Check the internet connection and try again.")
METHOD_TEXT = ("Sen's slope; Mann-Kendall test with variance scaled by lag 1 autocorrelation "
               "(effective sample size); Benjamini-Hochberg FDR on maps")


class BadRequest(ValueError):
    """The request itself is wrong (unknown measurement, impossible box)."""


class RegionTooLarge(ValueError):
    """Too many new tiles to fetch at once: the user should zoom in."""


class SourceUnavailable(RuntimeError):
    """NASA could not be reached and the data is not in the local cache."""


def _names(codes) -> str:
    """Plain names for a list of measurement codes: "a, b and c"."""
    names = [_VARS[c][0] for c in codes]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def variable_info(code: str) -> dict:
    if code not in _VARS:
        raise BadRequest(f"Unknown measurement {code}. Choose one of: {', '.join(_VARS)}.")
    name, unit, _, _ = _VARS[code]
    return {"code": code, "name": name, "unit": unit, "source": SOURCE}


def variables() -> dict:
    return {"version": VERSION, "period": PERIOD, "variables": [
        {**variable_info(c), "point": True, "region": _VARS[c][3],
         "world": (WORLD_DIR / f"{c}_annual.npz").exists()} for c in _VARS]}


# ---------- small helpers ----------

def _num(v, nd: int = 4):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


def _grid(a: np.ndarray, nd: int) -> list:
    """2D array -> nested lists, NaN -> null (JSON has no NaN)."""
    a = np.round(np.asarray(a, dtype=np.float64), nd)
    return [[None if not np.isfinite(v) else v for v in row] for row in a.tolist()]


def _fmt(v: float, nd: int) -> str:
    return f"{abs(v):.{nd}f}"


def _p_text(p: float, letter: str = "p") -> str:
    return f"{letter} < 0.001" if p < 0.001 else f"{letter} = {p:.3f}"


def luck_percent(p: float) -> str:
    """p as a percentage: how often a trend at least this strong appears when nothing is changing."""
    if p < 0.001:
        return "less than 0.1%"
    return f"{100 * p:.1f}%" if p < 0.0995 else f"{100 * p:.0f}%"


def _range_text(slope: float, lo: float, hi: float, nd: int) -> str:
    """The 95% range in words. Sizes only when it is all on one side; signed when it crosses zero."""
    if lo < 0 < hi:
        return f"95% range from {lo:+.{nd}f} to {hi:+.{nd}f}, so it only just clears zero"
    a, b = sorted((abs(lo), abs(hi)))
    return f"95% range {a:.{nd}f} to {b:.{nd}f}"


def _trend_line(annual: np.ndarray, slope_per_decade: float | None) -> list[dict]:
    """Two end points of the Sen line through the series (intercept = median of what is left)."""
    if slope_per_decade is None:
        return []
    t = np.arange(len(annual))
    per_year = slope_per_decade / 10
    icpt = float(np.nanmedian(annual - per_year * t))
    return [{"t": YEARS[0], "v": round(icpt, 4)}, {"t": YEARS[-1], "v": round(icpt + per_year * t[-1], 4)}]


def _series(annual: np.ndarray) -> list[dict]:
    return [{"t": y, "v": _num(v)} for y, v in zip(YEARS, annual)]


def _trend_block(annual: np.ndarray) -> dict:
    """Trend of one series as JSON. For a single place the level uses p (one test, no FDR needed)."""
    res = T.trend_one(annual)
    level = int(T.confidence_levels(np.array([np.nan if res["p"] is None else res["p"]]))[0])
    cp = T.change_point(annual, YEARS) if level > 0 else None
    return {
        "period": PERIOD,
        "slope_per_decade": _num(res["slope"]),
        "slope_low": _num(res["slope_lo"]),
        "slope_high": _num(res["slope_hi"]),
        "p": _num(res["p"], 5),
        "level": level,
        "level_name": "no data" if level < 0 else T.LEVEL_NAMES[level],
        "significant": level > 0,
        "direction": T.direction(res["slope"], level),
        "change_point_year": cp["year"] if cp else None,
        "n_years": res["n_years"],
        "mean": _num(res["mean"]),
        "method": METHOD_TEXT,
    }


def sentence(var: dict, trend: dict, where: str = "here") -> str:
    """Plain language summary built ONLY from the computed numbers."""
    code, name, unit = var["code"], var["name"], var["unit"]
    nd = _VARS[code][2]
    if trend["level"] < 0 or trend["slope_per_decade"] is None:
        return f"There is not enough NASA data {where} to measure a trend in {name}."
    slope = trend["slope_per_decade"]
    size = f"{_fmt(slope, nd)} {unit} per decade"
    luck = luck_percent(trend["p"])
    start = trend["period"][:4]
    if trend["level"] == 0:
        move = "a rise" if slope > 0 else "a fall" if slope < 0 else "no net change"
        return (f"Since {start}, {name} {where} shows {move} of {size}, but this is not proven: with nothing "
                f"really changing, normal year to year variation gives a trend this strong {luck} of the time.")
    verb = "rose" if slope > 0 else "fell"
    rng = _range_text(slope, trend["slope_low"], trend["slope_high"], nd)
    text = (f"Since {start}, {name} {where} {verb} by {size} ({rng}). "
            f"{trend['level_name'].capitalize()} that this is a real change: with nothing really changing, "
            f"a trend this strong would appear by luck only {luck} of the time.")
    if trend.get("change_point_year"):
        text += f" The level shifted around {trend['change_point_year']}."
    return text


# ---------- data access ----------

@lru_cache(maxsize=8)
def _egypt_monthly(var: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Egypt grid from the repo as (lats, lons, values[lat, lon, month]). Works with no internet."""
    import pandas as pd
    df = pd.read_parquet(EGYPT_TABLE, filters=[("variable", "==", var)])
    wide = df.pivot(index=["lat", "lon"], columns="time", values="value").sort_index().sort_index(axis=1)
    lats = np.array(sorted(df["lat"].unique()))
    lons = np.array(sorted(df["lon"].unique()))
    return lats, lons, wide.to_numpy(dtype=np.float32).reshape(len(lats), len(lons), -1)


def _in_egypt(lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> bool:
    return (EGYPT_BOX[0] <= lat_min and lat_max <= EGYPT_BOX[1]
            and EGYPT_BOX[2] <= lon_min and lon_max <= EGYPT_BOX[3])


def _missing_tiles(var: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> int:
    t = world_src.TILE
    la0s = range(int(np.floor(lat_min / t)) * t, int(np.ceil(lat_max / t)) * t, t)
    lo0s = range(int(np.floor(lon_min / t)) * t, int(np.ceil(lon_max / t)) * t, t)
    return sum(not world_src.tile_path(var, la, lo).exists()
               for la in la0s for lo in lo0s if -90 <= la < 90 and -180 <= lo < 180)


def region_data(var: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> dict:
    """Monthly grid for a box: Egypt from the repo, anything else live from NASA (cached on disk)."""
    variable_info(var)
    if not _VARS[var][3]:
        raise BadRequest(f"Trend maps are not available for {_VARS[var][0]} yet. Click a place to see its trend "
                         f"there, or pick another measurement for the map.")
    if not (-90 <= lat_min < lat_max <= 90 and -180 <= lon_min < lon_max <= 180):
        raise BadRequest("The selected area is not a valid box: south must be below north and west below east "
                         "(latitude -90 to 90, longitude -180 to 180).")
    if _in_egypt(lat_min, lat_max, lon_min, lon_max) and EGYPT_TABLE.exists():
        lats, lons, values = _egypt_monthly(var)
        r = (lats >= lat_min) & (lats <= lat_max)
        c = (lons >= lon_min) & (lons <= lon_max)
        return {"lats": lats[r], "lons": lons[c], "values": values[r][:, c], "from": "repo"}
    missing = _missing_tiles(var, lat_min, lat_max, lon_min, lon_max)
    if missing > MAX_NEW_TILES:
        raise RegionTooLarge(f"This area is too large to load in one go for {_VARS[var][0]}: it needs {missing} blocks "
                             f"of NASA data that are not saved on this computer yet (the limit is {MAX_NEW_TILES}). "
                             f"Choose a smaller country or area.")
    try:
        res = world_src.region_monthly(var, lat_min, lat_max, lon_min, lon_max)
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    except Exception as exc:
        raise SourceUnavailable(NOT_REACHABLE) from exc
    return {"lats": res["lats"], "lons": res["lons"], "values": res["values"],
            "from": "cache" if missing == 0 else "nasa"}


def point_data(var: str, lat: float, lon: float) -> dict:
    """Monthly series of the grid cell containing the point: repo, tile cache, or NASA point API."""
    try:
        cell_lat, cell_lon = point_src.snap(lat, lon)
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    if _VARS[var][3]:
        if _in_egypt(cell_lat, cell_lat, cell_lon, cell_lon) and EGYPT_TABLE.exists():
            lats, lons, values = _egypt_monthly(var)
            i, j = int(np.argmin(np.abs(lats - cell_lat))), int(np.argmin(np.abs(lons - cell_lon)))
            return {"lat": cell_lat, "lon": cell_lon, "values": values[i, j], "from": "repo"}
        t = world_src.TILE
        la0 = min(int(np.floor(cell_lat / t)) * t, 80)
        lo0 = min(int(np.floor(cell_lon / t)) * t, 170)
        tile = world_src.tile_path(var, la0, lo0)
        if tile.exists() and not point_src.cache_path(cell_lat, cell_lon).exists():
            with np.load(tile) as z:
                hit = np.where((np.abs(z["lats"] - cell_lat) < 0.01) & (np.abs(z["lons"] - cell_lon) < 0.01))[0]
                if len(hit):
                    return {"lat": cell_lat, "lon": cell_lon, "values": z["values"][hit[0]], "from": "cache"}
    try:
        res = point_src.point_monthly(cell_lat, cell_lon)
    except Exception as exc:
        raise SourceUnavailable(NOT_REACHABLE) from exc
    if var not in res["values"]:
        raise SourceUnavailable(f"NASA has no {_VARS[var][0]} data for this place.")
    return {"lat": cell_lat, "lon": cell_lon, "values": res["values"][var],
            "from": "cache" if res["cached"] else "nasa"}


# ---------- the three answers ----------

def point_trend(variable: str, lat: float, lon: float) -> dict:
    """Trend of one measurement at one place (the grid cell containing the point)."""
    t0 = time.perf_counter()
    var = variable_info(variable)
    data = point_data(variable, lat, lon)
    annual = T.annual_means(data["values"])
    trend = _trend_block(annual)
    out = {
        "version": VERSION, "kind": "trend_point", "variable": var,
        "location": {"lat": lat, "lon": lon, "cell_lat": data["lat"], "cell_lon": data["lon"]},
        "series": _series(annual),
        "trend_line": _trend_line(annual, trend["slope_per_decade"]),
        "trend": trend,
        "sentence": sentence(var, trend),
        "caution": None,
        "data_from": data["from"],
        "seconds": 0.0,
    }
    if variable == "PRECTOTCORR" and trend["mean"] is not None and trend["mean"] < ARID_MM_DAY:
        out["caution"] = ("Rain here is close to zero, so even a confident rain trend is a very small "
                          "amount of water. Read it with care.")
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out


def _map_block(annual: np.ndarray) -> tuple[dict, dict]:
    """Trend map arrays for [lat, lon, year] plus the cell counts."""
    res = T.trend_grid(annual)
    q = T.fdr_bh(res["p"])
    level = T.confidence_levels(q)
    slope = res["slope"]
    has = level >= 0
    sig = level > 0
    n = int(has.sum())
    counts = {
        "cells": int(level.size), "with_data": n,
        "increasing": int((sig & (slope > 0)).sum()),
        "decreasing": int((sig & (slope < 0)).sum()),
        "not_proven": int((level == 0).sum()),
        "strong": int((level == 2).sum()), "moderate": int((level == 1).sum()),
        "median_slope_per_decade": _num(np.nanmedian(slope[has])) if n else None,
    }
    return {"slope": slope, "p": res["p"], "q": q, "level": level, "mean": res["mean"]}, counts


def _region_sentence(var: dict, c: dict, place: str | None = None) -> str:
    if not c["with_data"]:
        return f"There is no NASA data for {var['name']} in {place or 'this region'}."
    pct = lambda k: f"{100 * c[k] / c['with_data']:.0f}%"   # noqa: E731
    whose = f"{place}'s" if place else "this region's"
    return (f"Since {T.START_YEAR}, {var['name']} is rising with convincing evidence in {pct('increasing')} "
            f"of {whose} {c['with_data']} grid cells and falling in {pct('decreasing')}. "
            f"In the other {pct('not_proven')} a change is not proven.")


def _country_mask(iso: str, lats: np.ndarray, lons: np.ndarray) -> tuple[str, np.ndarray]:
    """(country name, mask [lat, lon]) of the cells that touch the country."""
    try:
        name, mask = borders.country_mask(iso, lats, lons, world_src.LAT_STEP, world_src.LON_STEP)
    except borders.UnknownCountry as exc:
        raise BadRequest(f"Unknown country code {iso}. Use the 3 letter ISO code, for example EGY.") from exc
    if not mask.any():
        raise BadRequest(f"{name} is not inside the selected area.")
    return name, mask


@lru_cache(maxsize=64)
def _region_trend(variable: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float,
                  country: str | None = None) -> dict:
    var = variable_info(variable)
    data = region_data(variable, lat_min, lat_max, lon_min, lon_max)
    lats, lons = data["lats"], data["lons"]
    if len(lats) == 0 or len(lons) == 0:
        raise BadRequest("The selected area is smaller than one grid cell. Make it at least 0.5 x 0.625 degrees.")
    annual = T.annual_means(data["values"])
    place = None
    if country:
        # Cells outside the country become "no data" BEFORE testing, so the false discovery
        # correction, the counts and the average all cover the country only.
        place, mask = _country_mask(country, lats, lons)
        annual = np.where(mask[:, :, None], annual, np.nan)
    m, counts = _map_block(annual)
    if country:
        counts["cells"] = int(mask.sum())
    nd = _VARS[variable][2] + 2

    # Region average (cells weighted by their real area) for the chart.
    w = np.cos(np.radians(lats))[:, None, None] * np.isfinite(annual)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_series = np.nansum(annual * w, axis=(0, 1)) / w.sum(axis=(0, 1))
    mean_trend = _trend_block(mean_series)

    arid = variable == "PRECTOTCORR" and counts["with_data"] and \
        float(np.nanmean(m["mean"] < ARID_MM_DAY)) > 0.5
    return {
        "version": VERSION, "kind": "trend_region", "variable": var, "period": PERIOD,
        "bbox": {"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max},
        "country": {"iso": country, "name": place} if country else None,
        "grid": {
            "lats": [float(v) for v in lats], "lons": [float(v) for v in lons],
            "lat_step": world_src.LAT_STEP, "lon_step": world_src.LON_STEP,
            "slope_per_decade": _grid(m["slope"], nd),
            "p": _grid(m["p"], 5), "q": _grid(m["q"], 5),
            "level": m["level"].tolist(),
        },
        "levels": {"-1": "no data", "0": T.LEVEL_NAMES[0], "1": T.LEVEL_NAMES[1], "2": T.LEVEL_NAMES[2]},
        "summary": counts,
        "mean_series": _series(mean_series),
        "mean_trend_line": _trend_line(mean_series, mean_trend["slope_per_decade"]),
        "mean_trend": mean_trend,
        "sentence": _region_sentence(var, counts, place),
        "mean_sentence": sentence(var, mean_trend, where=f"averaged over {place or 'this region'}"),
        "caution": ("Most of this region gets almost no rain, so rain trends here are very small "
                    "amounts of water. Read them with care.") if arid else None,
        "method": METHOD_TEXT,
        "data_from": data["from"],
    }


def region_trend(variable: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float,
                 country: str | None = None) -> dict:
    """Trend map for every grid cell inside a box, as a compact grid (rows = lats, columns = lons).

    country (ISO 3 letter code, optional): keep only the cells that touch that country. Cells outside
    it are "no data", and the correction for many places, the counts and the average use the country only.
    """
    t0 = time.perf_counter()
    iso = country.strip().upper() if country and country.strip() else None
    out = dict(_region_trend(variable, float(lat_min), float(lat_max), float(lon_min), float(lon_max), iso))
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out


def world_trend(variable: str = "T2M", stride: int = 2) -> dict:
    """Whole Earth trend overview from the yearly world grid (computed once, then kept on disk).

    stride = 2 keeps every second cell in each direction (1 x 1.25 degrees) to keep the answer small.
    """
    var = variable_info(variable)
    src = WORLD_DIR / f"{variable}_annual.npz"
    if not src.exists():
        ready = [c for c in _VARS if (WORLD_DIR / f"{c}_annual.npz").exists()]
        only = f"It is ready for {_names(ready)} only. " if ready else ""
        raise BadRequest(f"The whole Earth map is not available for {var['name']} yet. {only}"
                         f"Pick a country or click a place to see this measurement.")
    if stride not in (1, 2, 4, 8):
        raise BadRequest("stride must be 1, 2, 4 or 8")
    out_file = OUTPUTS / f"world_{variable}_s{stride}.json"
    if out_file.exists() and out_file.stat().st_mtime >= src.stat().st_mtime:
        saved = json.loads(out_file.read_text())
        if saved.get("version") == VERSION:
            return saved
    with np.load(src) as z:
        annual, lats, lons = z["values"], z["lats"], z["lons"]
    m, counts = _map_block(annual)                     # FDR over the full grid, then thin it out
    s = slice(None, None, stride)
    out = {
        "version": VERSION, "kind": "trend_world", "variable": var, "period": PERIOD,
        "grid": {
            "lats": [float(v) for v in lats[s]], "lons": [float(v) for v in lons[s]],
            "lat_step": world_src.LAT_STEP * stride, "lon_step": world_src.LON_STEP * stride,
            "slope_per_decade": _grid(m["slope"][s, s], _VARS[variable][2] + 1),
            "level": m["level"][s, s].tolist(),
        },
        "levels": {"-1": "no data", "0": T.LEVEL_NAMES[0], "1": T.LEVEL_NAMES[1], "2": T.LEVEL_NAMES[2]},
        "summary": counts,
        "sentence": _region_sentence(var, counts).replace("this region's", "the world's"),
        "method": METHOD_TEXT,
    }
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, separators=(",", ":")))
    return out


def main() -> None:
    """`python run.py trends`: warm up everything the demo needs and print a short report."""
    for code in [c for c in _VARS if _VARS[c][3]]:
        r = region_trend(code, *EGYPT_BOX)
        s = r["summary"]
        print(f"Egypt {code:12s} rising {s['increasing']:3d}  falling {s['decreasing']:3d}  "
              f"not proven {s['not_proven']:3d}  ({r['seconds']} s)")
    for code in _VARS:
        if (WORLD_DIR / f"{code}_annual.npz").exists():
            t0 = time.perf_counter()
            w = world_trend(code)
            print(f"World {code}: {w['summary']['with_data']} cells, saved to ml/outputs/ "
                  f"({time.perf_counter() - t0:.1f} s)")


if __name__ == "__main__":
    main()
