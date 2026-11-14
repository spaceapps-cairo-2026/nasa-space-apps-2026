"""Build dist/cropshift_backend.zip: everything the UI needs to run the backend, nothing else.

Run:  python run.py package
The zip unpacks to one folder, `cropshift_backend/`, that works on its own.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "cropshift_backend.zip"
TOP = "cropshift_backend"

FILES = ["run.py", "requirements.txt", "conftest.py", ".gitignore"]
FOLDERS = ["api", "ml", "contracts", "tests", "app", "data/processed", "data/crops"]
DATA_SCRIPTS = ["data/power_point_fetch.py", "data/power_world_fetch.py", "data/power_fetch.py", "data/README.md"]
DOCS = ["docs/METHODS.md", "docs/DECISIONS.md"]
SKIP_PARTS = {"__pycache__", "outputs", "artifacts", ".pytest_cache"}
# ml/outputs holds local caches (skipped) and the two files the app reads (always shipped: the crop model's Egypt
# outlook for the farming tabs and the checks for "How we know"; without them the API falls back to the fixtures).
OUTPUTS = ["ml/outputs/farming_EGY.json", "ml/outputs/validation.json"]

README = """# CropShift Earth backend (trend engine + API), contract v0.6

This folder runs on its own. It answers: how much is a NASA measurement changing at a place,
and how confident are we that the change is real and not normal year to year variation.

## Run it (Windows, PowerShell, Python 3.10+)

    python run.py setup      install the Python packages (once)
    python run.py check      run the tests (must be green)
    python run.py mock       API on example answers, no internet needed  -> http://localhost:8000
    python run.py api        API on real data                            -> http://localhost:8000

Interactive API docs: http://localhost:8000/docs

## Merge with the UI

- Put the UI files in `app/` (replace what is there; `app/vendor/` has Plotly and Leaflet bundled).
  The API serves `app/index.html` at `/`. If the UI runs elsewhere, call the API by URL: CORS is open for GET.
- The UI only needs 4 calls. Full details, colors, errors and timings: **`contracts/api.md`**.

      GET /api/variables
      GET /api/trend/point?lat=30.04&lon=31.24&variable=T2M
      GET /api/trend/region?lat_min=22&lat_max=32&lon_min=25&lon_max=35&variable=T2M
      GET /api/trend/world?variable=T2M&stride=2

- Exact JSON shapes: `contracts/trend.schema.json`. Real example answers: `contracts/fixtures/trend_*.json`.
- Build the UI against `python run.py mock` first (always the same answers), then switch to `python run.py api`.

## What is live and what is local

- Egypt (lat 22 to 32, lon 25 to 35): in this folder, instant, works with no internet.
- Any other point: fetched from NASA POWER on first use (about 1.5 s), then cached in `data/cache/`.
- Any other region: fetched on first use (about 5 s per 10 x 10 degree tile), then cached. Show a
  loading message. More than 12 new tiles at once returns HTTP 413: ask the user to zoom in.
- World overview: average air temperature only (in this folder).

## Rules the UI must keep

- Show the confidence level ("strong evidence", "moderate evidence", "not proven"), with p or q on hover.
  Never show it as "X% true": p is how often such a trend appears when nothing is changing.
- Say "not proven", never "no change". Show `caution` when it is not null. Show `sentence` as is.

## Where things are

- `ml/trends.py`   the trend engine (arrays in, arrays out)
- `ml/live.py`     gets the data and builds the JSON answers
- `api/main.py`    the endpoints
- `data/`          NASA fetch scripts and the Egypt + world temperature data
- `docs/METHODS.md` section 0: the method, why it was chosen, and its measured error rates
"""


# The crop model's training material and the v2 rollback stay in git; the backend runs v3 only.
SKIP_CROP_MODEL = {"retrain", "training", "crop_suitability_v2.npz", "crop_engine_v2.py", "metrics.json"}


def wanted(path: Path) -> bool:
    if "crop_model" in path.parts and set(path.parts) & SKIP_CROP_MODEL:
        return False
    return path.is_file() and not (set(path.parts) & SKIP_PARTS) and path.suffix != ".pyc"


def main() -> None:
    paths = [ROOT / f for f in FILES + DATA_SCRIPTS + DOCS + OUTPUTS]
    for folder in FOLDERS:
        paths += sorted(p for p in (ROOT / folder).rglob("*") if wanted(p))
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(f"{TOP}/README.md", README)
        for p in paths:
            z.write(p, f"{TOP}/{p.relative_to(ROOT).as_posix()}")
    print(f"{OUT.relative_to(ROOT)}: {len(paths) + 1} files, {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
