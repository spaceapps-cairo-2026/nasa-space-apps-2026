"""Lane C: download NASA POWER monthly climate grids for Egypt (no login needed).

NASA POWER serves MERRA-2 (NASA's atmospheric reanalysis model) and satellite-derived
variables on a 0.5 x 0.5 degree grid. Over Egypt that is 357 grid cells.

Output: data/processed/power_monthly.parquet (long/tidy format)
    columns: cell_id, lat, lon, time (YYYY-MM), variable, value

Run:  python data/power_fetch.py            (about 1 to 3 minutes)
Raw JSON is cached in data/cache/power/, so re-runs are instant and work offline.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "power"
OUT = ROOT / "data" / "processed" / "power_monthly.parquet"

# Egypt bounding box (POWER regional requests allow up to 10 x 10 degrees)
BBOX = {"latitude-min": 22, "latitude-max": 32, "longitude-min": 25, "longitude-max": 35}
START, END = 2001, 2025

VARIABLES = {
    "T2M": "Air temperature at 2 m (C)",
    "T2M_MAX": "Daily max air temperature at 2 m, monthly mean (C)",
    "PRECTOTCORR": "Precipitation, bias corrected (mm/day)",
    "GWETTOP": "Topsoil wetness (0 = dry, 1 = saturated)",
    "GWETROOT": "Root zone soil wetness (0 to 1)",
    "RH2M": "Relative humidity at 2 m (%)",
}

URL = ("https://power.larc.nasa.gov/api/temporal/monthly/regional"
       "?parameters={p}&community=AG&latitude-min={latitude-min}&latitude-max={latitude-max}"
       "&longitude-min={longitude-min}&longitude-max={longitude-max}&start={s}&end={e}&format=JSON")


def download(param: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{param}_{START}_{END}.json"
    if path.exists():
        return json.loads(path.read_text())
    url = URL.replace("{p}", param).replace("{s}", str(START)).replace("{e}", str(END))
    for k, v in BBOX.items():
        url = url.replace("{" + k + "}", str(v))
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                data = json.loads(r.read())
            if not data.get("features"):
                raise RuntimeError(f"No features returned: {str(data)[:300]}")
            path.write_text(json.dumps(data))
            return data
        except Exception as exc:  # network hiccup: retry
            print(f"  {param}: attempt {attempt + 1} failed ({exc}); retrying")
            time.sleep(5)
    raise SystemExit(f"Could not download {param}. Check internet, then rerun (cached ones are kept).")


def to_rows(param: str, data: dict) -> list[dict]:
    rows = []
    for f in data["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        cell = f"p_{lat:.1f}_{lon:.1f}"
        for key, val in f["properties"]["parameter"][param].items():
            if key.endswith("13"):          # month "13" is the annual mean, skip it
                continue
            rows.append({
                "cell_id": cell, "lat": lat, "lon": lon,
                "time": f"{key[:4]}-{key[4:]}", "variable": param,
                "value": None if val is None or val <= -999 else float(val),
            })
    return rows


def summary(df, verb: str) -> None:
    print(f"{verb} {OUT}: {len(df):,} rows, {df.cell_id.nunique()} cells, "
          f"{df.time.min()} to {df.time.max()}, variables {sorted(df.variable.unique())}")
    print(f"missing values: {df.value.isna().mean():.2%}")


def main() -> None:
    import sys

    import pandas as pd

    # The parquet file is committed to git. Rebuilding it on another laptop can change its
    # bytes (library versions), which would show up as a modified file, so only rebuild on request.
    if OUT.exists() and "--force" not in sys.argv:
        summary(pd.read_parquet(OUT), "already built (use --force to rebuild)")
        return

    rows: list[dict] = []
    for p in VARIABLES:
        print(f"downloading {p} ...")
        rows += to_rows(p, download(p))
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    summary(df, "wrote")


if __name__ == "__main__":
    main()
