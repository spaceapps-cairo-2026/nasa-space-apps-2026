"""Lane C: request MODIS NDVI + land surface temperature for 5 Egypt areas via NASA AppEEARS.

AppEEARS cuts NASA satellite products to an area and date range and returns ready files.
Processing runs on NASA's side and can take hours, so SUBMIT EARLY.

Usage (PowerShell):
    $env:EARTHDATA_USERNAME="your_user"; $env:EARTHDATA_PASSWORD="your_password"
    python data/appeears_request.py check      # no login: verifies products/layers exist
    python data/appeears_request.py submit     # submits one task per area
    python data/appeears_request.py status     # shows progress
    python data/appeears_request.py download   # downloads finished files

Task ids are saved in data/cache/appeears/tasks.json so any teammate with the
same login can check status or download.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://appeears.earthdatacloud.nasa.gov/api"
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "appeears"
TASKS = CACHE / "tasks.json"

START, END = "01-01-2003", "12-31-2025"   # AppEEARS wants MM-DD-YYYY

LAYERS = [
    {"product": "MOD13A3.061", "layer": "_1_km_monthly_NDVI"},
    {"product": "MOD13A3.061", "layer": "_1_km_monthly_pixel_reliability"},
    {"product": "MYD11A2.061", "layer": "LST_Day_1km"},
    {"product": "MYD11A2.061", "layer": "QC_Day"},
]

# name: (lat_min, lat_max, lon_min, lon_max). Approximate; check on NASA Worldview.
AREAS = {
    "east_owainat": (22.2, 22.9, 28.2, 28.9),
    "toshka": (22.4, 23.1, 30.9, 31.9),
    "new_delta": (30.1, 30.9, 29.6, 30.6),
    "greater_cairo": (29.85, 30.25, 31.05, 31.55),
    "delta_core": (30.6, 31.3, 30.6, 31.6),
}


def request(url: str, method: str = "GET", data: dict | None = None, headers: dict | None = None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    if body is not None:
        req.add_header("Content-Type", "application/json")
    return urllib.request.urlopen(req, timeout=120)


def get_json(url: str, **kw) -> dict | list:
    with request(url, **kw) as r:
        return json.loads(r.read())


def login() -> dict:
    try:  # read EARTHDATA_* from the repo's .env file if present (PowerShell variables still win)
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
    except ImportError:
        pass
    user, pw = os.getenv("EARTHDATA_USERNAME"), os.getenv("EARTHDATA_PASSWORD")
    if not user or not pw:
        raise SystemExit("Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD first (see top of this file).")
    auth = base64.b64encode(f"{user}:{pw}".encode()).decode()
    hdr = {"Authorization": f"Basic {auth}", "Content-Length": "0"}
    try:
        token = get_json(f"{API}/login", method="POST", headers=hdr)["token"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Earthdata login failed ({e.code}). Check username/password, and that you "
                         "accepted the AppEEARS terms once at https://appeears.earthdatacloud.nasa.gov") from e
    return {"Authorization": f"Bearer {token}"}


def box(name: str, lat0: float, lat1: float, lon0: float, lon1: float) -> dict:
    ring = [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]
    return {"type": "Feature", "properties": {"name": name},
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def payload(name: str) -> dict:
    return {
        "task_type": "area",
        "task_name": f"spaceapps26_{name}",
        "params": {
            "dates": [{"startDate": START, "endDate": END}],
            "layers": LAYERS,
            "geo": {"type": "FeatureCollection", "features": [box(name, *AREAS[name])]},
            "output": {"format": {"type": "netcdf4"}, "projection": "geographic"},
        },
    }


def check() -> None:
    for prod in sorted({l["product"] for l in LAYERS}):
        layers = get_json(f"{API}/product/{prod}")
        for l in LAYERS:
            if l["product"] == prod:
                ok = l["layer"] in layers
                print(f"{'OK ' if ok else 'MISSING'} {prod} {l['layer']}")
                if not ok:
                    raise SystemExit("Layer name wrong; fix LAYERS.")
    for name in AREAS:
        p = payload(name)
        assert p["params"]["geo"]["features"][0]["geometry"]["coordinates"][0][0] == \
            p["params"]["geo"]["features"][0]["geometry"]["coordinates"][0][-1]
    print(f"{len(AREAS)} area payloads valid. Ready to submit.")


def submit() -> None:
    check()
    headers = login()
    CACHE.mkdir(parents=True, exist_ok=True)
    tasks = json.loads(TASKS.read_text()) if TASKS.exists() else {}
    for name in AREAS:
        if name in tasks:
            print(f"{name}: already submitted ({tasks[name]})")
            continue
        r = get_json(f"{API}/task", method="POST", data=payload(name), headers=headers)
        tasks[name] = r["task_id"]
        TASKS.write_text(json.dumps(tasks, indent=2))
        print(f"{name}: submitted, task {r['task_id']} ({r.get('status')})")
    print(f"Saved task ids to {TASKS}. Check later with: python data/appeears_request.py status")


def status() -> dict:
    headers = login()
    tasks = json.loads(TASKS.read_text())
    states = {}
    for name, tid in tasks.items():
        s = get_json(f"{API}/task/{tid}", headers=headers)
        states[name] = s.get("status")
        print(f"{name:14s} {s.get('status')}")
    return states


def download() -> None:
    headers = login()
    tasks = json.loads(TASKS.read_text())
    for name, tid in tasks.items():
        s = get_json(f"{API}/task/{tid}", headers=headers)
        if s.get("status") != "done":
            print(f"{name}: not ready ({s.get('status')}), skipping")
            continue
        out = CACHE / name
        out.mkdir(parents=True, exist_ok=True)
        for f in get_json(f"{API}/bundle/{tid}", headers=headers)["files"]:
            target = out / Path(f["file_name"]).name
            if target.exists() and target.stat().st_size == f.get("file_size", -1):
                continue
            print(f"{name}: downloading {f['file_name']} ({f.get('file_size', 0) / 1e6:.1f} MB)")
            with request(f"{API}/bundle/{tid}/{f['file_id']}", headers=headers) as r, open(target, "wb") as fh:
                while chunk := r.read(1 << 20):
                    fh.write(chunk)
    print(f"Done. Files in {CACHE}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"check": check, "submit": submit, "status": status, "download": download}.get(
        cmd, lambda: print(__doc__))()
