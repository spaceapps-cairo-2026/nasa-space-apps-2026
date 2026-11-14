"""Lane A: live trends. Gets the data (Egypt from the repo, anywhere else from NASA with a disk
cache), runs the trend engine, and returns the JSON shapes defined in contracts/api.md (v0.5).

This is what the API calls:
    point_trend(variable, lat, lon)                               -> "trend_point"
    region_trend(variable, lat_min, lat_max, lon_min, lon_max, country=None)   -> "trend_region"
    world_trend(variable="T2M", stride=2)                         -> "trend_world"
    variables()                                                   -> the measurement picker
Each trend function also takes start_year and end_year: the trend is measured over those years only
(at least 10 years, inside 2001 to 2025). Left out = the whole record.

Speed: Egypt and anything fetched before answer in well under a second. A new point waits about
1 to 2 s for NASA; a new region about 5 s per 10 x 10 degree tile.
"""
from __future__ import annotations

import json
import sys
import time
import warnings
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

VERSION = "0.7"
PERIOD = f"{T.START_YEAR}-{T.END_YEAR}"
YEARS = list(range(T.START_YEAR, T.END_YEAR + 1))
SOURCE = "NASA POWER (MERRA-2), monthly, 0.5 x 0.625 degree grid"
EGYPT_BOX = (22.0, 32.0, 25.0, 35.0)             # the grid committed in data/processed/
EGYPT_TABLE = ROOT / "data" / "processed" / "power_monthly.parquet"
WORLD_DIR = ROOT / "data" / "processed" / "world"
OUTPUTS = ROOT / "ml" / "outputs"
MAX_NEW_TILES = 12                               # more missing tiles than this = "zoom in" (about 1 minute)
ARID_MM_DAY = 0.1                                # below this, rain trends get a caution note
# Rain in this record jumps around 2015 in many places at once (Egypt: median 2.9 times the 2001 to 2014
# level in 80% of grid cells, change years clustered in 2014 to 2016; Ethiopia about doubles). A step that
# sudden and widespread looks like a change in how the record is made, not real rain. Every rain answer says so.
RAIN_CAUTION = ("Read rain trends with care: in this NASA POWER rain record, rain jumps around 2015 in many "
                "places at once (across Egypt it is about 3 times higher after 2015 in most grid cells). A jump "
                "that sudden and widespread may come from how the record is made rather than from real rain, "
                "so check a rain trend against rain gauges before relying on it.")

# Moisture records (rain, humidity, soil wetness) break around 2015 in the same places. Checked against an
# independent record (ERA5 reanalysis, Open-Meteo archive, 16 places, Sat 14 Nov; docs/DECISIONS.md): air
# temperature agrees everywhere (correlation 0.72 to 0.98); where NASA POWER's own rain is >= 1.5 times higher
# after 2015, or where it hardly rains, POWER humidity and topsoil wetness move the opposite way to ERA5
# (Asyut, Cairo, Kharga humidity +1.3 to +1.5 points per decade in POWER, -0.7 to -1.4 in ERA5). There these
# four records are "not reliable here": the numbers are shown, never called evidence of a change.
MOISTURE = ("PRECTOTCORR", "RH2M", "GWETTOP", "GWETROOT")
BREAK_RATIO = 1.5            # rain 2015-2025 vs 2001-2014 at the place
DRY_MM_DAY = 0.1             # under this mean rain the ratio means nothing (Kharga 0.001 mm a day)
BREAK_YEAR = 2015
LEVEL_UNRELIABLE = -2

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
# Units as words in sentences (the API's `unit` field stays as it is). Wetness has no unit: it is a 0 to 1 scale.
_UNIT_TEXT = {"C": " °C", "mm/day": " mm per day", "%": " percentage points"}
_SCALE = "fraction (0 to 1)"                     # wetness: said once, after the total
NOT_REACHABLE = ("NASA data is not reachable right now and this place is not saved on this computer yet. "
                 "Check the internet connection and try again.")
METHOD_TEXT = ("Sen's slope; Mann-Kendall test with variance scaled by lag 1 autocorrelation of what is left "
               "after a smooth curve (effective sample size; a straight line for ranges under 20 years); "
               "Benjamini-Hochberg FDR on maps")


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


def window(start_year: int | None = None, end_year: int | None = None) -> tuple[int, int]:
    """The years a trend is measured over. None = the first / last year of the record."""
    s = T.START_YEAR if start_year is None else int(start_year)
    e = T.END_YEAR if end_year is None else int(end_year)
    if not (T.START_YEAR <= s <= e <= T.END_YEAR):
        raise BadRequest(f"Choose years between {T.START_YEAR} and {T.END_YEAR}, with the first year before the last.")
    if e - s + 1 < T.MIN_RANGE_YEARS:
        raise BadRequest(f"A trend needs at least {T.MIN_RANGE_YEARS} years: fewer years cannot tell a real change "
                         f"from normal ups and downs. Choose a longer range.")
    return s, e


def _cut(annual: np.ndarray, s: int, e: int) -> np.ndarray:
    """The chosen years of a [..., year] array that covers the whole record."""
    return annual[..., s - T.START_YEAR:e - T.START_YEAR + 1]


def variables() -> dict:
    return {"version": VERSION, "period": PERIOD, "start_year": T.START_YEAR, "end_year": T.END_YEAR,
            "min_range_years": T.MIN_RANGE_YEARS, "variables": [
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


def _trend_line(annual: np.ndarray, trend: dict) -> list[dict]:
    """Two end points (first and last chosen year) of the Sen line; intercept = median of what is left."""
    if trend["slope_per_decade"] is None:
        return []
    s, e = trend["start_year"], trend["end_year"]
    part = _cut(annual, s, e)
    t = np.arange(len(part))
    per_year = trend["slope_per_decade"] / 10
    icpt = float(np.nanmedian(part - per_year * t))
    return [{"t": s, "v": round(icpt, 4)}, {"t": e, "v": round(icpt + per_year * t[-1], 4)}]


def _series(annual: np.ndarray) -> list[dict]:
    return [{"t": y, "v": _num(v)} for y, v in zip(YEARS, annual)]


def rain_break(rain_annual: np.ndarray) -> np.ndarray | bool:
    """True where the NASA POWER rain record shows the 2015 break (or it hardly rains). rain_annual is
    [..., year] for 2001 to 2025 in mm per day; where there is no rain record the answer is False."""
    k = BREAK_YEAR - T.START_YEAR
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pre = np.nanmean(rain_annual[..., :k], axis=-1)
        post = np.nanmean(rain_annual[..., k:], axis=-1)
        mean = np.nanmean(rain_annual, axis=-1)
        out = (mean < DRY_MM_DAY) | (post >= BREAK_RATIO * pre)
    return np.where(np.isfinite(mean), out, False)


def _unreliable_reason(var: dict, ratio: float | None, mean: float | None) -> str:
    if mean is not None and mean < DRY_MM_DAY:
        why = f"it hardly ever rains here ({mean * 365:.0f} mm a year in this record)"
    else:
        why = f"rain in the same NASA record is {ratio:.1f} times higher from 2015 than before"
    return (f"Not reliable here: {why}. In such places NASA's rain, humidity and soil wetness records jump around "
            f"2015 together, which looks like a change in how the record is made: an independent climate record "
            f"(ERA5) shows no such jump, and across Egypt it shows humidity falling, not rising. We show the "
            f"numbers but do not call this a real change. Air temperature is not affected.")


def _mark_unreliable(trend: dict) -> dict:
    t = dict(trend)
    t.update(level=LEVEL_UNRELIABLE, level_name="not reliable", significant=False, direction="not reliable",
             change_point_year=None)
    return t


def _trend_block(annual: np.ndarray, s: int = T.START_YEAR, e: int = T.END_YEAR) -> dict:
    """Trend of one series over the years s to e, as JSON.

    annual covers the whole record. For a single place the level uses p (one test, no FDR needed).
    """
    part = _cut(annual, s, e)
    res = T.trend_one(part)
    level = int(T.confidence_levels(np.array([np.nan if res["p"] is None else res["p"]]))[0])
    cp = T.change_point(part, range(s, e + 1)) if level > 0 else None
    total = lambda v: None if v is None else _num(v / 10 * (e - s))   # noqa: E731
    return {
        "period": f"{s}-{e}",
        "start_year": s, "end_year": e,
        "change_total": total(res["slope"]),
        "change_low": total(res["slope_lo"]),
        "change_high": total(res["slope_hi"]),
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
    """Plain language summary built ONLY from the computed numbers.

    The headline is the total change over the chosen years, so the 95% range is given for that total too
    (the same numbers the app shows); the rate per decade follows it.
    """
    code, name = var["code"], var["name"]
    unit = _UNIT_TEXT.get(var["unit"], "" if var["unit"] == _SCALE else f" {var['unit']}")
    unit_total = " on the 0 to 1 scale" if var["unit"] == _SCALE else unit
    nd = _VARS[code][2]
    if trend["level"] == -1 or trend["slope_per_decade"] is None:
        if code.startswith("GWET") and trend.get("mean") in (None, 1.0):   # all missing, or the sea fill value 1
            return f"Soil wetness exists only on land. NASA has no {name} for this place (sea or ice), so there is no trend to measure."
        return f"There is not enough NASA data {where} to measure a trend in {name}."
    slope = trend["slope_per_decade"]
    if trend["level"] == LEVEL_UNRELIABLE:
        start, end = (int(y) for y in trend["period"].split("-"))
        tot = trend.get("change_total")
        tot = slope * (end - start) / 10 if tot is None else tot
        return (f"In the NASA POWER record, {name} {where} changes by {_fmt(tot, nd)}{unit_total} from {start} to {end}, "
                f"but this record is not reliable {where} (see the note below), so this is not evidence of a real change.")
    luck = luck_percent(trend["p"])
    start, end = (int(y) for y in trend["period"].split("-"))
    when = f"Since {start}" if end == T.END_YEAR else f"From {start} to {end}"
    span = (end - start) / 10
    tot = trend.get("change_total")
    tot = slope * span if tot is None else tot
    total = f"{_fmt(tot, nd)}{unit_total} in total"
    size = f"{_fmt(slope, nd)}{unit} per decade"
    if trend["level"] == 0:
        move = "a rise" if slope > 0 else "a fall" if slope < 0 else "no net change"
        return (f"{when}, {name} {where} shows {move} of {total} ({size}), but this is not proven: with nothing "
                f"really changing, normal year to year variation gives a trend this strong {luck} of the time.")
    verb = "rose" if slope > 0 else "fell"
    lo, hi = trend.get("change_low"), trend.get("change_high")
    if lo is None or hi is None:
        lo, hi = trend["slope_low"] * span, trend["slope_high"] * span
    rng = _range_text(tot, lo, hi, nd)
    text = (f"{when}, {name} {where} {verb} by {total} ({rng}), a rate of {size}. "
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


def region_annual(var: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> dict:
    """Yearly means [lat, lon, year] for a box. Outside Egypt, a measurement with a committed world grid
    (data/processed/world/<var>_annual.npz, every cell on Earth, 2001 to 2025; air temperature today) is read from
    it, never downloaded: any laptop maps any country (Russia included) in under a second with no internet, every
    laptop gives the same answer, and the map matches the Whole Earth layer, which uses the same file. Egypt keeps
    its repo table. Other measurements come from region_data (NASA, saved on disk)."""
    src = WORLD_DIR / f"{var}_annual.npz"
    if (src.exists() and _VARS.get(var, (None,) * 4)[3] and -90 <= lat_min < lat_max <= 90
            and -180 <= lon_min < lon_max <= 180 and not (_in_egypt(lat_min, lat_max, lon_min, lon_max) and EGYPT_TABLE.exists())):
        with np.load(src) as z:
            lats, lons = z["lats"].astype(float), z["lons"].astype(float)
            r = (lats >= lat_min) & (lats <= lat_max)
            c = (lons >= lon_min) & (lons <= lon_max)
            annual = z["values"][r][:, c].astype(float)
            years = [int(y) for y in z["years"]]
        if years != list(range(T.START_YEAR, T.END_YEAR + 1)):
            raise SourceUnavailable(f"The saved world grid covers {years[0]} to {years[-1]}, not {T.START_YEAR} to {T.END_YEAR}.")
        return {"lats": lats[r], "lons": lons[c], "annual": annual, "from": "world"}
    d = region_data(var, lat_min, lat_max, lon_min, lon_max)
    return {"lats": d["lats"], "lons": d["lons"], "annual": T.annual_means(d["values"]), "from": d["from"]}


def _world_point(var: str, lat: float, lon: float) -> dict | None:
    """Yearly series of the cell from the committed world grid (outside Egypt, for measurements that have one):
    a click anywhere answers at once with no internet, the same on every laptop, and agrees with the Whole Earth
    layer. Egypt keeps its repo table; other measurements use point_data (NASA, saved on disk)."""
    src = WORLD_DIR / f"{var}_annual.npz"
    if not src.exists():
        return None
    try:
        cell_lat, cell_lon = point_src.snap(lat, lon)
    except ValueError:
        return None                                       # point_data raises the plain error
    if _in_egypt(cell_lat, cell_lat, cell_lon, cell_lon) and EGYPT_TABLE.exists():
        return None
    with np.load(src) as z:
        if [int(y) for y in z["years"]] != list(range(T.START_YEAR, T.END_YEAR + 1)):
            return None
        i = int(np.argmin(np.abs(z["lats"] - cell_lat)))
        j = int(np.argmin(np.abs(z["lons"] - cell_lon)))
        if abs(float(z["lats"][i]) - cell_lat) > 0.01 or abs(float(z["lons"][j]) - cell_lon) > 0.01:
            return None
        annual = z["values"][i, j].astype(float)
    return {"lat": cell_lat, "lon": cell_lon, "annual": annual, "from": "world"}


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

def point_trend(variable: str, lat: float, lon: float,
                start_year: int | None = None, end_year: int | None = None) -> dict:
    """Trend of one measurement at one place (the grid cell containing the point).

    start_year, end_year: measure the trend over these years only. The series always has every year.
    """
    t0 = time.perf_counter()
    var = variable_info(variable)
    s, e = window(start_year, end_year)
    data = _world_point(variable, lat, lon) or point_data(variable, lat, lon)
    annual = data["annual"] if "annual" in data else T.annual_means(data["values"])
    trend = _trend_block(annual, s, e)
    out = {
        "version": VERSION, "kind": "trend_point", "variable": var,
        "location": {"lat": lat, "lon": lon, "cell_lat": data["lat"], "cell_lon": data["lon"]},
        "series": _series(annual),
        "trend_line": _trend_line(annual, trend),
        "trend": trend,
        "sentence": sentence(var, trend),
        "caution": RAIN_CAUTION if variable == "PRECTOTCORR" else None,
        "data_from": data["from"],
        "seconds": 0.0,
    }
    if variable == "PRECTOTCORR" and trend["mean"] is not None and trend["mean"] < ARID_MM_DAY:
        out["caution"] = ("Rain here is close to zero, so even a confident rain trend is a very small "
                          "amount of water. " + RAIN_CAUTION)
    if variable in MOISTURE and trend["level"] >= 0:
        out.update(_point_reliability(var, out, lat, lon, annual))
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out


def _point_reliability(var: dict, out: dict, lat: float, lon: float, annual: np.ndarray) -> dict:
    """Moisture answers: is the record reliable at this place? (See MOISTURE.)"""
    try:
        if var["code"] == "PRECTOTCORR":
            rain = np.asarray(annual, float)
        else:
            rain = np.asarray(T.annual_means(point_data("PRECTOTCORR", lat, lon)["values"]), float)
    except (BadRequest, SourceUnavailable):
        return {"reliability": {"reliable": None, "reason": "The rain record needed for this check is not available right now."}}
    k = BREAK_YEAR - T.START_YEAR
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pre, post, mean = float(np.nanmean(rain[:k])), float(np.nanmean(rain[k:])), float(np.nanmean(rain))
    ratio = post / pre if pre > 0 else None
    if not bool(rain_break(rain)):
        return {"reliability": {"reliable": True, "reason": None, "rain_ratio_after_2015": _num(ratio, 2)}}
    reason = _unreliable_reason(var, ratio, mean)
    trend = _mark_unreliable(out["trend"])
    return {"trend": trend, "sentence": sentence(var, trend), "caution": reason,
            "reliability": {"reliable": False, "reason": reason, "rain_ratio_after_2015": _num(ratio, 2)}}


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


def _region_sentence(var: dict, c: dict, place: str | None = None,
                     s: int = T.START_YEAR, e: int = T.END_YEAR) -> str:
    if not c["with_data"]:
        return f"There is no NASA data for {var['name']} in {place or 'this region'}."
    pct = lambda k: f"{100 * c[k] / c['with_data']:.0f}%"   # noqa: E731
    whose = f"{place}'s" if place else "this region's"
    when = f"Since {s}" if e == T.END_YEAR else f"From {s} to {e}"
    return (f"{when}, {var['name']} is rising with convincing evidence in {pct('increasing')} "
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
                  country: str | None = None, s: int = T.START_YEAR, e: int = T.END_YEAR) -> dict:
    var = variable_info(variable)
    data = region_annual(variable, lat_min, lat_max, lon_min, lon_max)
    lats, lons = data["lats"], data["lons"]
    if len(lats) == 0 or len(lons) == 0:
        raise BadRequest("The selected area is smaller than one grid cell. Make it at least 0.5 x 0.625 degrees.")
    annual = data["annual"]
    place = None
    if country:
        # Cells outside the country become "no data" BEFORE testing, so the false discovery
        # correction, the counts and the average all cover the country only.
        place, mask = _country_mask(country, lats, lons)
        annual = np.where(mask[:, :, None], annual, np.nan)
    withheld, share_withheld, rain_ok = 0, 0.0, True
    annual_all = annual
    if variable in MOISTURE:
        # Cells whose rain record breaks in 2015 are left out BEFORE testing (see MOISTURE).
        try:
            rain = annual if variable == "PRECTOTCORR" else \
                region_annual("PRECTOTCORR", lat_min, lat_max, lon_min, lon_max)["annual"]
            land = np.isfinite(annual).any(axis=-1)
            broken = rain_break(rain) & land
            withheld = int(broken.sum())
            share_withheld = withheld / max(int(land.sum()), 1)
            annual = np.where(broken[:, :, None], np.nan, annual)
        except (BadRequest, SourceUnavailable, RegionTooLarge):
            rain_ok = False
    m, counts = _map_block(_cut(annual, s, e))
    if country:
        counts["cells"] = int(mask.sum())
    if variable in MOISTURE:
        counts["not_reliable"] = withheld
    nd = _VARS[variable][2] + 2

    # Region average (cells weighted by their real area) for the chart. When most cells are left out (see
    # MOISTURE), the average of all cells is still shown, labelled not reliable.
    src = annual_all if share_withheld > 0.5 else annual
    w = np.cos(np.radians(lats))[:, None, None] * np.isfinite(src)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_series = np.nansum(np.nan_to_num(src) * w, axis=(0, 1)) / w.sum(axis=(0, 1))
    mean_trend = _trend_block(mean_series, s, e)
    if share_withheld > 0.5 and mean_trend["level"] >= 0:
        mean_trend = _mark_unreliable(mean_trend)

    arid = variable == "PRECTOTCORR" and counts["with_data"] and \
        float(np.nanmean(m["mean"] < ARID_MM_DAY)) > 0.5
    caution = ("Most of this region gets almost no rain, so rain trends here are very small "
               "amounts of water. " + RAIN_CAUTION) if arid else RAIN_CAUTION if variable == "PRECTOTCORR" else None
    if withheld:
        caution = (f"{withheld} grid cells are left out of this map: there NASA's rain record jumps from 2015 (or it "
                   f"hardly rains), and its {var['name']} moves with that break while an independent climate record "
                   f"(ERA5) does not." + (" The cells shown have a steady rain record." if counts["with_data"] else "")
                   + (" The average for the whole area is not reliable for the same reason." if share_withheld > 0.5 else ""))
    elif variable in MOISTURE and not rain_ok:
        caution = (f"The rain record needed to check {var['name']} here is not available right now, so read this map "
                   f"with care: where NASA's rain jumps from 2015, {var['name']} moves with it.")
    return {
        "version": VERSION, "kind": "trend_region", "variable": var, "period": f"{s}-{e}",
        "start_year": s, "end_year": e,
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
        "mean_trend_line": _trend_line(mean_series, mean_trend),
        "mean_trend": mean_trend,
        "sentence": (f"{var['name'].capitalize()} is not mapped in {place or 'this region'}: in all {withheld} grid cells "
                     f"NASA's record is not reliable (see the note below)." if withheld and not counts["with_data"]
                     else _region_sentence(var, counts, place, s, e)),
        "mean_sentence": sentence(var, mean_trend, where=f"across {place or 'this region'}"),
        "caution": caution,
        "method": METHOD_TEXT,
        "data_from": data["from"],
    }


def _at_least_one_cell(lo: float, hi: float, step: float, floor: float, ceil: float) -> tuple[float, float]:
    """A valid box narrower than one grid cell (a small country such as Luxembourg) is widened around its
    centre to just over one cell, so it always holds a cell centre. Invalid boxes are left for the checks."""
    if not lo < hi or hi - lo >= step:
        return lo, hi
    mid, half = (lo + hi) / 2, step * 0.501
    return max(floor, mid - half), min(ceil, mid + half)


def region_trend(variable: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float,
                 country: str | None = None, start_year: int | None = None, end_year: int | None = None) -> dict:
    """Trend map for every grid cell inside a box, as a compact grid (rows = lats, columns = lons).

    country (ISO 3 letter code, optional): keep only the cells that touch that country. Cells outside
    it are "no data", and the correction for many places, the counts and the average use the country only.
    """
    t0 = time.perf_counter()
    s, e = window(start_year, end_year)
    iso = country.strip().upper() if country and country.strip() else None
    lat_min, lat_max = _at_least_one_cell(float(lat_min), float(lat_max), world_src.LAT_STEP, -90.0, 90.0)
    lon_min, lon_max = _at_least_one_cell(float(lon_min), float(lon_max), world_src.LON_STEP, -180.0, 180.0)
    out = dict(_region_trend(variable, lat_min, lat_max, lon_min, lon_max, iso, s, e))
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out


def world_trend(variable: str = "T2M", stride: int = 2,
                start_year: int | None = None, end_year: int | None = None) -> dict:
    """Whole Earth trend overview from the yearly world grid (computed once, then kept on disk).

    stride = 2 keeps every second cell in each direction (1 x 1.25 degrees) to keep the answer small.
    """
    var = variable_info(variable)
    s0, e0 = window(start_year, end_year)
    src = WORLD_DIR / f"{variable}_annual.npz"
    if not src.exists():
        ready = [c for c in _VARS if (WORLD_DIR / f"{c}_annual.npz").exists()]
        only = f"It is ready for {_names(ready)} only. " if ready else ""
        raise BadRequest(f"The whole Earth map is not available for {var['name']} yet. {only}"
                         f"Pick a country or click a place to see this measurement.")
    if stride not in (1, 2, 4, 8):
        raise BadRequest("stride must be 1, 2, 4 or 8")
    whole = (s0, e0) == (T.START_YEAR, T.END_YEAR)
    out_file = OUTPUTS / (f"world_{variable}_s{stride}.json" if whole else f"world_{variable}_s{stride}_{s0}_{e0}.json")
    if out_file.exists() and out_file.stat().st_mtime >= src.stat().st_mtime:
        saved = json.loads(out_file.read_text())
        if saved.get("version") == VERSION:
            return saved
    with np.load(src) as z:
        annual, lats, lons = z["values"], z["lats"], z["lons"]
    m, counts = _map_block(_cut(annual, s0, e0))       # FDR over the full grid, then thin it out
    s = slice(None, None, stride)
    out = {
        "version": VERSION, "kind": "trend_world", "variable": var, "period": f"{s0}-{e0}",
        "start_year": s0, "end_year": e0,
        "grid": {
            "lats": [float(v) for v in lats[s]], "lons": [float(v) for v in lons[s]],
            "lat_step": world_src.LAT_STEP * stride, "lon_step": world_src.LON_STEP * stride,
            "slope_per_decade": _grid(m["slope"][s, s], _VARS[variable][2] + 1),
            "level": m["level"][s, s].tolist(),
        },
        "levels": {"-1": "no data", "0": T.LEVEL_NAMES[0], "1": T.LEVEL_NAMES[1], "2": T.LEVEL_NAMES[2]},
        "summary": counts,
        "sentence": _region_sentence(var, counts, None, s0, e0).replace("this region's", "the world's"),
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
