"""Lane C, task C1: NASA POWER monthly values for ONE point anywhere on Earth (no login needed).

One request returns all measurements for the point (about 1.3 s). The answer is kept on disk in
data/cache/power_point/, so each place is only ever fetched once and the demo works offline.

NASA POWER serves the value of the grid cell (0.5 x 0.625 degrees) that contains the point, so
the point is first snapped to its cell center: every click inside one cell reuses one cache file.

Use:
    from power_point_fetch import point_monthly
    r = point_monthly(30.04, 31.24)          # Cairo
    r["values"]["T2M"]                       # 300 monthly values from 2001-01, NaN = no data
    r["lat"], r["lon"], r["cached"]
Run:  python data/power_point_fetch.py 30.04 31.24
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "power_point"

START, END = 2001, 2025
N_MONTHS = (END - START + 1) * 12
LAT_STEP, LON_STEP = 0.5, 0.625

VARIABLES = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "GWETTOP", "GWETROOT", "RH2M"]

URL = ("https://power.larc.nasa.gov/api/temporal/monthly/point"
       "?parameters={p}&community=AG&latitude={lat}&longitude={lon}&start={s}&end={e}&format=JSON")


def snap(lat: float, lon: float) -> tuple[float, float]:
    """Center of the grid cell that contains the point."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("need -90 <= lat <= 90 and -180 <= lon <= 180")
    cell_lat = round(round(lat / LAT_STEP) * LAT_STEP, 3)
    cell_lon = round(round((lon + 180) / LON_STEP) % 576 * LON_STEP - 180, 3)
    return cell_lat, cell_lon


def cache_path(cell_lat: float, cell_lon: float) -> Path:
    return CACHE / f"lat{cell_lat:+07.2f}_lon{cell_lon:+08.3f}.npz"


def fetch_json(cell_lat: float, cell_lon: float, tries: int = 3, timeout: int = 30) -> dict:
    url = URL.format(p=",".join(VARIABLES), lat=cell_lat, lon=cell_lon, s=START, e=END)
    err = ""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                data = json.loads(r.read())
            if data.get("properties", {}).get("parameter"):
                return data
            err = f"no data in answer: {str(data)[:150]}"
        except urllib.error.HTTPError as exc:
            err = f"HTTP {exc.code}"
        except Exception as exc:                 # network hiccup
            err = str(exc)[:120]
        if attempt < tries - 1:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"NASA POWER point {cell_lat},{cell_lon} failed after {tries} tries: {err}")


def to_arrays(data: dict) -> dict[str, np.ndarray]:
    out = {}
    for var, months in data["properties"]["parameter"].items():
        values = np.full(N_MONTHS, np.nan, dtype=np.float32)
        for key, val in months.items():
            month = int(key[4:])
            if month > 12 or val is None or val <= -999:     # month 13 is the annual mean
                continue
            values[(int(key[:4]) - START) * 12 + month - 1] = val
        out[var] = values
    return out


def point_monthly(lat: float, lon: float) -> dict:
    """Monthly values of every measurement for the grid cell containing (lat, lon).

    Returns {"lat", "lon" (cell center), "months": ["2001-01", ...],
             "values": {variable: float32 array [300]}, "cached": bool}.
    """
    cell_lat, cell_lon = snap(lat, lon)
    path = cache_path(cell_lat, cell_lon)
    cached = path.exists()
    if not cached:
        arrays = to_arrays(fetch_json(cell_lat, cell_lon))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.stem}.{os.getpid()}_{threading.get_ident()}.tmp.npz")
        np.savez_compressed(tmp, **arrays)
        try:
            tmp.replace(path)                    # never leave a half written file behind
        except OSError:
            tmp.unlink(missing_ok=True)
            if not path.exists():
                raise
    with np.load(path) as z:
        values = {var: z[var] for var in z.files}
    months = [f"{START + m // 12}-{m % 12 + 1:02d}" for m in range(N_MONTHS)]
    return {"lat": cell_lat, "lon": cell_lon, "months": months, "values": values, "cached": cached}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    t0 = time.time()
    res = point_monthly(float(sys.argv[1]), float(sys.argv[2]))
    print(f"cell {res['lat']}, {res['lon']}  cached={res['cached']}  {time.time() - t0:.2f} s")
    for name, vals in res["values"].items():
        print(f"  {name:12s} {int(np.isfinite(vals).sum())} valid months, mean {np.nanmean(vals):.3f}")
