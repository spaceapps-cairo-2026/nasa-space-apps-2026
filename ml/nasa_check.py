"""Lane A: our NASA POWER trends checked against two other NASA records (Methods page, Check 5).

    python run.py nasa-check     downloads the two files once (no login, about 70 MB), writes
                                 ml/outputs/nasa_check.json and ml/outputs/gistemp250_annual.npz

1. Temperature: NASA GISTEMP v4, 250 km smoothing (GHCN v4 weather stations, 2 x 2 degree boxes). It is built from
   thermometers, not from a weather model, so it is an independent check of POWER's air temperature (MERRA-2).
   Every Egypt box with stations: our D1 engine on both records, same years, same test.
   Whole world: in land boxes where both records have 20+ years, do they agree on the direction?
2. Rain: GPCP v2.3 monthly (satellites + rain gauges, the Global Precipitation Climatology Project led at NASA
   Goddard, distributed by NOAA PSL). Does it show the 2015 jump that POWER's PRECTOTCORR shows over Egypt?

Raw files go to data/raw/nasa_check/ (gitignored, rule 6: too big). The yearly GISTEMP means 2001 to 2025 (small)
are kept in ml/outputs/gistemp250_annual.npz so that ml/crop_outlook.py works on any laptop without the download.
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
import farming as fao  # noqa: E402  (Egypt grid and border helpers)
import trends as T     # noqa: E402  (decision D1 engine)

RAW = ROOT / "data" / "raw" / "nasa_check"
GISTEMP_URL = "https://data.giss.nasa.gov/pub/gistemp/gistemp250_GHCNv4.nc.gz"
GPCP_URL = "https://downloads.psl.noaa.gov/Datasets/gpcp/precip.mon.mean.nc"
GISTEMP_NC = RAW / "gistemp250_GHCNv4.nc"
GPCP_NC = RAW / "gpcp_precip.mon.mean.nc"
GISTEMP_NPZ = ROOT / "ml" / "outputs" / "gistemp250_annual.npz"
OUT = ROOT / "ml" / "outputs" / "nasa_check.json"
START, END = 2001, 2025
JUMP_YEAR = 2015                     # before = 2001 to 2014, after = 2016 to 2025 (same split as ml/crosscheck.py)
DAYS = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


# ---------- download (once) ----------

def _get(url: str, dest: Path) -> None:
    if dest.exists():
        return
    RAW.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if url.endswith(".gz"):
        with gzip.open(tmp, "rb") as g, open(dest, "wb") as f:
            shutil.copyfileobj(g, f)
        tmp.unlink()
    else:
        tmp.rename(dest)


def download() -> None:
    _get(GISTEMP_URL, GISTEMP_NC)
    _get(GPCP_URL, GPCP_NC)


def _monthly(path: Path, var: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """(lats, lons, values [lat, lon, month], 'YYYY-MM' per month) for START to END, lats ascending, lons -180 to 180."""
    import xarray as xr      # only this script needs it; the app does not
    ds = xr.open_dataset(path, drop_variables=["time_bnds"])
    da = ds[var].sel(time=slice(f"{START}-01-01", f"{END}-12-31"))
    if float(da.lat[0]) > float(da.lat[-1]):
        da = da.isel(lat=slice(None, None, -1))
    lons = da.lon.values.astype(float)
    if lons.max() > 180:
        da = da.assign_coords(lon=((da.lon + 180) % 360) - 180).sortby("lon")
    months = [str(t)[:7] for t in da.time.values]
    vals = np.moveaxis(da.values.astype(float), 0, -1)
    return da.lat.values.astype(float), da.lon.values.astype(float), vals, months


def _full_years(vals: np.ndarray, months: list[str]) -> np.ndarray:
    want = [f"{y}-{m:02d}" for y in range(START, END + 1) for m in range(1, 13)]
    idx = {m: i for i, m in enumerate(months)}
    out = np.full(vals.shape[:-1] + (len(want),), np.nan)
    for k, m in enumerate(want):
        if m in idx:
            out[..., k] = vals[..., idx[m]]
    return out


def gistemp_annual() -> dict:
    """Yearly GISTEMP 250 km anomalies 2001 to 2025 on its 2 degree grid (engine rule: 9+ valid months a year)."""
    if GISTEMP_NC.exists():
        lats, lons, vals, months = _monthly(GISTEMP_NC, "tempanomaly")
        annual = T.annual_means(_full_years(vals, months)).astype(np.float32)
        GISTEMP_NPZ.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(GISTEMP_NPZ, lats=lats, lons=lons, years=np.arange(START, END + 1), values=annual)
    with np.load(GISTEMP_NPZ) as z:
        return {k: z[k] for k in z.files}


def station_warming(lats: np.ndarray, lons: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each (lat, lon) of a grid: GISTEMP warming per decade, its evidence level (D1, FDR over the boxes that
    hold the grid's cells) and the box index. NaN / -1 where the box has fewer than 20 years of station data."""
    g = gistemp_annual()
    bi = np.abs(g["lats"][None, :] - lats[:, None]).argmin(1)
    bj = np.abs(g["lons"][None, :] - lons[:, None]).argmin(1)
    boxes = sorted({(int(a), int(b)) for a in bi for b in bj})
    series = np.array([g["values"][a, b] for a, b in boxes], dtype=float)
    res = T.trend_grid(series[:, None, :])
    slope, p = res["slope"][:, 0], res["p"][:, 0]
    level = T.confidence_levels(T.fdr_bh(p))
    where = {box: n for n, box in enumerate(boxes)}
    k = np.array([[where[(a, b)] for b in bj] for a in bi])
    return slope[k], level[k], k


# ---------- the checks ----------

def egypt_temperature() -> dict:
    """GISTEMP boxes over Egypt vs the POWER cells inside each box: same engine, same years."""
    lats, lons, cube = fao.monthly_cube("T2M")
    inside = _egypt_cells(lats, lons)
    power = T.annual_means(cube.reshape(*cube.shape[:2], -1))
    g = gistemp_annual()
    rows = []
    for a, la in enumerate(g["lats"]):
        for b, lo in enumerate(g["lons"]):
            m = inside & (np.abs(lats[:, None] - la) <= 1) & (np.abs(lons[None, :] - lo) <= 1)
            if not m.any():
                continue
            gs = g["values"][a, b].astype(float)
            if np.isfinite(gs).sum() < 20:
                continue
            ps = np.nanmean(power[m], axis=0)
            ok = np.isfinite(gs) & np.isfinite(ps)
            rows.append({"lat": float(la), "lon": float(lo), "power_cells": int(m.sum()),
                         "gistemp": T.trend_one(gs), "power": T.trend_one(ps),
                         "corr": float(np.corrcoef(gs[ok], ps[ok])[0, 1])})
    q_g = T.fdr_bh(np.array([r["gistemp"]["p"] for r in rows]))
    q_p = T.fdr_bh(np.array([r["power"]["p"] for r in rows]))
    lev_g, lev_p = T.confidence_levels(q_g), T.confidence_levels(q_p)
    for r, a, b in zip(rows, lev_g, lev_p):
        r["gistemp_level"], r["power_level"] = int(a), int(b)
    gs = np.array([r["gistemp"]["slope"] for r in rows])
    ps = np.array([r["power"]["slope"] for r in rows])
    w = np.array([r["power_cells"] for r in rows], dtype=float)
    return {
        "boxes": len(rows),
        "gistemp_per_decade": round(float((gs * w).sum() / w.sum()), 3),
        "power_per_decade": round(float((ps * w).sum() / w.sum()), 3),
        "gistemp_proven": int((lev_g > 0).sum()), "power_proven": int((lev_p > 0).sum()),
        "same_direction": int((np.sign(gs) == np.sign(ps)).sum()),
        "median_corr": round(float(np.median([r["corr"] for r in rows])), 2),
        "rows": [{"lat": r["lat"], "lon": r["lon"], "power_cells": r["power_cells"],
                  "gistemp": round(r["gistemp"]["slope"], 3), "gistemp_p": float(f"{r['gistemp']['p']:.2g}"),
                  "gistemp_level": r["gistemp_level"],
                  "power": round(r["power"]["slope"], 3), "power_p": float(f"{r['power']['p']:.2g}"),
                  "power_level": r["power_level"], "corr": round(r["corr"], 2)} for r in rows],
    }


def world_temperature() -> dict:
    """Every GISTEMP land box with 20+ years vs the POWER world grid cells inside it (committed T2M grid)."""
    g = gistemp_annual()
    with np.load(ROOT / "data" / "processed" / "world" / "T2M_annual.npz") as z:
        plats, plons, pv = z["lats"].astype(float), z["lons"].astype(float), z["values"].astype(float)
    bi = np.abs(g["lats"][None, :] - plats[:, None]).argmin(1)
    bj = np.abs(g["lons"][None, :] - plons[:, None]).argmin(1)
    gs, ps, wt = [], [], []
    for a in range(len(g["lats"])):
        ra = np.nonzero(bi == a)[0]
        if not len(ra):
            continue
        for b in range(len(g["lons"])):
            series = g["values"][a, b].astype(float)
            if np.isfinite(series).sum() < 20:
                continue
            cb = np.nonzero(bj == b)[0]
            block = pv[np.ix_(ra, cb)].reshape(-1, pv.shape[-1])
            block = block[np.isfinite(block).all(1)]
            if not len(block):
                continue
            gs.append(series)
            ps.append(block.mean(0))
            wt.append(np.cos(np.radians(g["lats"][a])))
    gs, ps, wt = np.array(gs), np.array(ps), np.array(wt)
    rg, rp = T.trend_grid(gs[:, None, :]), T.trend_grid(ps[:, None, :])
    sg, sp = rg["slope"][:, 0], rp["slope"][:, 0]
    lg, lp = T.confidence_levels(T.fdr_bh(rg["p"][:, 0])), T.confidence_levels(T.fdr_bh(rp["p"][:, 0]))
    proven_g = lg > 0
    return {
        "boxes": int(len(gs)),
        "same_direction_share": round(float(np.average(np.sign(sg) == np.sign(sp), weights=wt)), 3),
        "gistemp_proven_share": round(float(np.average(proven_g, weights=wt)), 3),
        "power_proven_share": round(float(np.average(lp > 0, weights=wt)), 3),
        "power_proven_where_gistemp_proven": round(float(np.average(lp[proven_g] > 0, weights=wt[proven_g])), 3),
        "opposite_proven": int(((lg > 0) & (lp > 0) & (np.sign(sg) != np.sign(sp))).sum()),
        "gistemp_mean_per_decade": round(float(np.average(sg, weights=wt)), 3),
        "power_mean_per_decade": round(float(np.average(sp, weights=wt)), 3),
        "slope_corr": round(float(np.corrcoef(sg, sp)[0, 1]), 2),
    }


def _egypt_cells(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    border = json.loads(fao.BORDER.read_text(encoding="utf-8"))["geometry"]
    polys = [border["coordinates"]] if border["type"] == "Polygon" else border["coordinates"]
    return np.array([[fao.touches_country(float(la), float(lo), polys) for lo in lons] for la in lats])


def egypt_rain() -> dict:
    """Egypt rain per year, POWER (repo table) vs GPCP v2.3 at the same cells. GPCP is 2.5 degrees, so each POWER cell
    reads the GPCP box that holds it; the north coast boxes include some sea."""
    lats, lons, cube = fao.monthly_cube("PRECTOTCORR")
    inside = _egypt_cells(lats, lons)
    power = (cube * DAYS).sum(-1)                                    # mm per year [lat, lon, year]
    glat, glon, gv, months = _monthly(GPCP_NC, "precip")
    gy = (_full_years(gv, months).reshape(*gv.shape[:2], -1, 12) * DAYS).sum(-1)
    areas = {"egypt": ("Egypt, all land cells", inside),
             "north_coast": ("Egypt's north coast (30.5 N and north)", inside & (lats[:, None] >= 30.5))}
    out = {}
    for key, (label, m) in areas.items():
        ii, jj = np.nonzero(m)
        p = np.nanmean(power[m], axis=0)
        g = np.nanmean([gy[np.abs(glat - lats[i]).argmin(), np.abs(glon - lons[j]).argmin()] for i, j in zip(ii, jj)], axis=0)
        cut = JUMP_YEAR - START
        row = {"label": label, "years": list(range(START, END + 1)),
               "power_mm": [round(float(v), 1) for v in p], "gpcp_mm": [round(float(v), 1) for v in g]}
        for name, s in (("power", p), ("gpcp", g)):
            before, after = float(np.nanmean(s[:cut])), float(np.nanmean(s[cut + 1:]))
            row[f"{name}_before"], row[f"{name}_after"] = round(before, 1), round(after, 1)
            row[f"{name}_jump"] = round(after / before, 2)
            cp = T.change_point(s, np.arange(START, END + 1))
            row[f"{name}_change_year"] = cp["year"] if cp else None
        out[key] = row
    return out


def plain(t: dict, w: dict, r: dict) -> tuple[str, str]:
    e = r["egypt"]
    temp = (f"Over Egypt, NASA's station record (GISTEMP, 250 km) warms {t['gistemp_per_decade']:+.2f} °C per decade from "
            f"{START} to {END}; our NASA POWER cells in the same {t['boxes']} areas of 2 by 2 degrees warm {t['power_per_decade']:+.2f}. "
            f"Both records go the same way in {t['same_direction']} of {t['boxes']} areas and their yearly values move "
            f"together (median correlation {t['median_corr']:.2f}). With the same test, the station record proves the "
            f"warming in {t['gistemp_proven']} of {t['boxes']} areas, POWER in {t['power_proven']}: POWER (a weather model, "
            f"MERRA-2) shows weaker warming than the thermometers over Egypt, so many 'not proven' cells in our maps are "
            f"too cautious, not a sign that Egypt is not warming.")
    rain = (f"Rain: POWER over Egypt is {e['power_jump']:.1f} times higher after 2015 than before "
            f"({e['power_before']:.0f} mm to {e['power_after']:.0f} mm a year). NASA's GPCP record (satellites and rain gauges) "
            f"at the same places changes by {e['gpcp_jump']:.2f} times ({e['gpcp_before']:.0f} mm to {e['gpcp_after']:.0f} mm). "
            f"The jump is in the POWER record, not in real rain, so the crop projections take this one-time step out of rain, "
            f"humidity and soil wetness before measuring their trend, and continue that trend from today's level.")
    return temp, rain


def run() -> dict:
    download()
    t, w, r = egypt_temperature(), world_temperature(), egypt_rain()
    temp, rain = plain(t, w, r)
    return {"title": "Our trends checked against NASA's station and satellite records", "period": [START, END],
            "sources": {"temperature": "NASA GISTEMP v4, 250 km smoothing (GHCN v4 stations), " + GISTEMP_URL,
                        "rain": "GPCP v2.3 monthly precipitation (satellites + gauges; NASA GSFC led, NOAA PSL), " + GPCP_URL},
            "egypt_temperature": t, "world_temperature": w, "egypt_rain": r,
            "plain_temperature": temp, "plain_rain": rain}


if __name__ == "__main__":
    res = run()
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(res["plain_temperature"])
    print(res["plain_rain"])
    print("world:", res["world_temperature"])
    print(f"wrote {OUT} and {GISTEMP_NPZ}")
