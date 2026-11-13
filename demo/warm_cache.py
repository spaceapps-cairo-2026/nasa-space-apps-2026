"""Load every place the tour and the demo use once, so nothing waits during recording or judging.

Start the app with real data first (python run.py api), then in a second window:
    python demo/warm_cache.py
NASA answers are kept on disk by the backend, so after this run every place below is instant.
Uses the same country boxes as the app (app/data/countries.geojson).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")

TOUR_COUNTRIES = ["EGY", "KEN"]                                     # used by the guided tour
DEMO_COUNTRIES = ["SAU", "MAR", "ETH", "TUR", "FRA", "DEU", "ESP", "ITA", "JPN", "MEX"]  # nice for a live demo
POINTS = {                                                          # tour point first
    "Aswan": (24.09, 32.90), "Cairo": (30.04, 31.24), "Alexandria": (31.20, 29.92), "Nairobi": (-1.29, 36.82),
    "Dubai": (25.20, 55.27), "Paris": (48.86, 2.35), "Tokyo": (35.68, 139.69), "New York": (40.71, -74.01),
    "Sao Paulo": (-23.55, -46.63), "Sydney": (-33.87, 151.21),
}
VARIABLES = ["T2M"]  # the tour uses air temperature; add more codes here if the demo shows them


def get(path: str, params: dict) -> tuple[int, float, str]:
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    t = time.time()
    try:
        with urllib.request.urlopen(url, timeout=300) as r:
            body = json.loads(r.read())
            note = body.get("sentence") or body.get("mean_sentence") or ""
            return r.status, time.time() - t, note[:90]
    except urllib.error.HTTPError as e:
        return e.code, time.time() - t, e.read().decode("utf-8", "replace")[:120]
    except Exception as e:  # server down, network
        return 0, time.time() - t, str(e)[:120]


def main() -> int:
    countries = {f["properties"]["iso"]: f["properties"] for f in
                 json.loads((ROOT / "app" / "data" / "countries.geojson").read_text(encoding="utf-8"))["features"]}
    status, _, note = get("/health", {})
    if status != 200:
        print(f"The app is not running at {BASE}. Start it with: python run.py api   ({note})")
        return 1
    failures = 0
    for var in VARIABLES:
        s, dt, note = get("/api/trend/world", {"variable": var, "stride": 2})
        print(f"{'OK ' if s == 200 else 'ERR'} {dt:5.1f}s  world {var}  {note}")
        failures += s != 200
        for iso in TOUR_COUNTRIES + DEMO_COUNTRIES:
            c = countries.get(iso)
            if not c:
                continue
            w, so, e, n = c["bbox"]
            s, dt, note = get("/api/trend/region", {"lat_min": so, "lat_max": n, "lon_min": w, "lon_max": e, "variable": var})
            print(f"{'OK ' if s == 200 else 'ERR'} {dt:5.1f}s  {c['name']:<14} {note}")
            failures += s != 200 and iso in TOUR_COUNTRIES
        for name, (lat, lon) in POINTS.items():
            s, dt, note = get("/api/trend/point", {"lat": lat, "lon": lon, "variable": var})
            print(f"{'OK ' if s == 200 else 'ERR'} {dt:5.1f}s  {name:<14} {note}")
            failures += s != 200
    for path in ("/api/farming", "/api/validation"):
        s, dt, _ = get(path, {"country": "EGY"} if "farming" in path else {})
        print(f"{'OK ' if s == 200 else 'ERR'} {dt:5.1f}s  {path}")
        failures += s != 200
    print("\nAll set: the tour and these places now load instantly." if not failures
          else f"\n{failures} request(s) failed; run again (finished ones stay cached).")
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
