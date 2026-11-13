"""Lane C: download NASA POWER monthly climate grids for the WHOLE WORLD (no login needed).

Why: F1 (trend explorer) must show trend maps anywhere on Earth, not only in Egypt.

The NASA POWER regional service returns at most a 10 x 10 degree box and one variable per
request, so the world is fetched as 648 tiles per variable (18 x 36). Each tile takes about
4 seconds. One variable is about 45 minutes with one worker, less with a few workers.

World grid: 361 latitudes (-90 to 90, step 0.5) x 576 longitudes (-180 to 179.375, step 0.625)
= 207,936 cells, 300 months (Jan 2001 to Dec 2025).

Files (all on the project drive):
  data/cache/power_world/<VAR>/lat<a>_lon<b>.npz   one tile, compact      (NOT in git, about 1 GB total)
  data/cache/power_world/<VAR>_monthly.npy         world, [lat, lon, month] (NOT in git, 250 MB each)
  data/processed/world/<VAR>_annual.npz            world, [lat, lon, year]  (in git, small)

Run:
  python run.py world                      download everything that is missing, then build
  python run.py world --variables T2M      only some variables (comma separated)
  python run.py world --status             show progress, download nothing
  python run.py world --build              only rebuild the world files from downloaded tiles
  python run.py world --workers 3          parallel downloads (default 3; use 1 if NASA slows us down)
Safe to stop (Ctrl+C) and rerun at any time: finished tiles are kept.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "power_world"
OUT = ROOT / "data" / "processed" / "world"

START, END = 2001, 2025
N_YEARS = END - START + 1
N_MONTHS = N_YEARS * 12
LAT_STEP, LON_STEP = 0.5, 0.625
LATS = np.round(np.arange(-90, 90 + LAT_STEP / 2, LAT_STEP), 3)      # 361 values
LONS = np.round(np.arange(-180, 180, LON_STEP), 3)                   # 576 values
TILE = 10
MIN_MONTHS_PER_YEAR = 9   # a year with fewer valid months has no annual mean (docs/METHODS.md)

# Download order = priority: a usable world temperature map exists after the first variable.
VARIABLES = {
    "T2M": "Air temperature at 2 m (C)",
    "PRECTOTCORR": "Precipitation, bias corrected (mm/day)",
    "T2M_MAX": "Daily max air temperature at 2 m, monthly mean (C)",
    "GWETROOT": "Root zone soil wetness (0 to 1)",
    "RH2M": "Relative humidity at 2 m (%)",
    "GWETTOP": "Topsoil wetness (0 = dry, 1 = saturated)",
}

URL = ("https://power.larc.nasa.gov/api/temporal/monthly/regional"
       "?parameters={p}&community=AG&latitude-min={la0}&latitude-max={la1}"
       "&longitude-min={lo0}&longitude-max={lo1}&start={s}&end={e}&format=JSON")


def tiles() -> list[tuple[int, int]]:
    """South-west corner of every 10 x 10 degree tile."""
    return [(la, lo) for la in range(-90, 90, TILE) for lo in range(-180, 180, TILE)]


def tile_path(var: str, la: int, lo: int) -> Path:
    return CACHE / var / f"lat{la:+04d}_lon{lo:+05d}.npz"


def lat_index(lat: float) -> int:
    return int(round((lat + 90) / LAT_STEP))


def lon_index(lon: float) -> int:
    return int(round((lon + 180) / LON_STEP)) % len(LONS)


def fetch_json(var: str, la: int, lo: int, tries: int = 6) -> dict:
    url = URL.format(p=var, la0=la, la1=la + TILE, lo0=lo, lo1=lo + TILE, s=START, e=END)
    wait = 5
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                data = json.loads(r.read())
            if data.get("features"):
                return data
            raise RuntimeError(f"no features: {str(data)[:200]}")
        except urllib.error.HTTPError as exc:
            if exc.code == 429:          # NASA says: too many requests, slow down
                wait = max(wait, 60)
            err = f"HTTP {exc.code}"
        except Exception as exc:         # network hiccup
            err = str(exc)[:120]
        if attempt < tries - 1:
            print(f"  {var} tile {la},{lo}: {err}; retry in {wait}s", flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 300)
    raise RuntimeError(f"{var} tile {la},{lo} failed after {tries} tries: {err}")


def to_arrays(var: str, data: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One tile as (lats, lons, values[cell, month]); missing values become NaN."""
    feats = data["features"]
    lats = np.array([f["geometry"]["coordinates"][1] for f in feats], dtype=np.float32)
    lons = np.array([f["geometry"]["coordinates"][0] for f in feats], dtype=np.float32)
    values = np.full((len(feats), N_MONTHS), np.nan, dtype=np.float32)
    for i, f in enumerate(feats):
        for key, val in f["properties"]["parameter"][var].items():
            month = int(key[4:])
            if month > 12 or val is None or val <= -999:   # month 13 is the annual mean
                continue
            values[i, (int(key[:4]) - START) * 12 + month - 1] = val
    return lats, lons, values


def download_tile(var: str, la: int, lo: int) -> str:
    path = tile_path(var, la, lo)
    if path.exists():
        return "cached"
    lats, lons, values = to_arrays(var, fetch_json(var, la, lo))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, lats=lats, lons=lons, values=values)
    tmp.replace(path)                    # never leave a half written tile behind
    return "downloaded"


def download(var: str, workers: int, limit: int | None) -> int:
    todo = [(la, lo) for la, lo in tiles() if not tile_path(var, la, lo).exists()]
    if limit is not None:
        todo = todo[:limit]
    total = len(tiles())
    done = total - len([t for t in tiles() if not tile_path(var, *t).exists()])
    if not todo:
        print(f"{var}: all {total} tiles already downloaded")
        return 0
    print(f"{var}: {done}/{total} tiles present, downloading {len(todo)} with {workers} worker(s)", flush=True)
    failed, t0 = 0, time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(download_tile, var, la, lo): (la, lo) for la, lo in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                fut.result()
            except Exception as exc:
                failed += 1
                print(f"  FAILED {exc}", flush=True)
            if n % 20 == 0 or n == len(todo):
                rate = (time.time() - t0) / n
                print(f"  {var}: {done + n - failed}/{total} tiles, "
                      f"about {rate * (len(todo) - n) / 60:.0f} min left for this variable", flush=True)
    return failed


def build(var: str) -> bool:
    """Combine tiles into the world monthly array (local) and the annual means file (for git)."""
    present = [t for t in tiles() if tile_path(var, *t).exists()]
    if not present:
        return False
    world = np.full((len(LATS), len(LONS), N_MONTHS), np.nan, dtype=np.float32)
    for la, lo in present:
        with np.load(tile_path(var, la, lo)) as z:
            rows = np.array([lat_index(v) for v in z["lats"]])
            cols = np.array([lon_index(v) for v in z["lons"]])
            world[rows, cols, :] = z["values"]
    np.save(CACHE / f"{var}_monthly.npy", world)

    by_year = world.reshape(len(LATS), len(LONS), N_YEARS, 12)
    valid = np.isfinite(by_year).sum(axis=3)
    with np.errstate(invalid="ignore", divide="ignore"):
        annual = np.nansum(by_year, axis=3) / valid
    annual[valid < MIN_MONTHS_PER_YEAR] = np.nan
    annual = np.round(annual, 3).astype(np.float32)

    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / f"{var}_annual.npz", values=annual, lats=LATS.astype(np.float32),
                        lons=LONS.astype(np.float32), years=np.arange(START, END + 1, dtype=np.int16))
    covered = np.isfinite(annual).any(axis=2).mean()
    size = (OUT / f"{var}_annual.npz").stat().st_size / 1e6
    note = "" if len(present) == len(tiles()) else f"  (PARTIAL: {len(present)}/{len(tiles())} tiles)"
    print(f"built {var}: {covered:.0%} of world cells have data, annual file {size:.1f} MB{note}")
    return True


def status(variables: list[str]) -> None:
    total = len(tiles())
    for var in variables:
        n = sum(tile_path(var, *t).exists() for t in tiles())
        built = "built" if (OUT / f"{var}_annual.npz").exists() else "not built"
        print(f"{var:12s} {n:3d}/{total} tiles  {built}")


def main() -> None:
    ap = argparse.ArgumentParser(description="NASA POWER world download")
    ap.add_argument("--variables", default=",".join(VARIABLES), help="comma separated, default all")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="download at most N tiles per variable (testing)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--build", action="store_true", help="only build, download nothing")
    args = ap.parse_args()
    variables = [v.strip() for v in args.variables.split(",") if v.strip()]
    unknown = [v for v in variables if v not in VARIABLES]
    if unknown:
        raise SystemExit(f"unknown variables {unknown}; choose from {list(VARIABLES)}")

    if args.status:
        status(variables)
        return
    failed = 0
    for var in variables:
        if not args.build:
            failed += download(var, args.workers, args.limit)
        build(var)
    status(variables)
    if failed:
        raise SystemExit(f"{failed} tiles failed. Rerun the same command: finished tiles are kept.")


if __name__ == "__main__":
    main()
