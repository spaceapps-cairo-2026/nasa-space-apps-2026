"""Generate contracts/fixtures/sample_predictions.json (contract v0.2, trend shaped).

Lane A runs this after every schema change so lanes B and C always have valid fake data.
The numbers are RANDOM. Nothing here is science. Places mimic the 5 Egypt areas.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contracts" / "fixtures" / "sample_predictions.json"

VARIABLES = [
    {"code": "NDVI", "name": "Plant greenness (NDVI)", "unit": "NDVI", "source": "MODIS MOD13A3"},
    {"code": "LST_DAY", "name": "Land surface temperature, day", "unit": "C", "source": "MODIS MYD11A2"},
    {"code": "T2M", "name": "Air temperature at 2 m", "unit": "C", "source": "MERRA-2 via NASA POWER"},
]

# name, lat, lon, fingerprint, ndvi sign, lst sign
AREAS = [
    ("East Owainat", 22.55, 28.55, "new farmland", +1, -1),
    ("Toshka", 22.75, 31.4, "new farmland", +1, -1),
    ("New Delta", 30.5, 30.1, "new farmland", +1, -1),
    ("Greater Cairo edge", 30.05, 31.3, "urban sprawl", -1, +1),
    ("Delta core", 30.95, 31.1, "stable farmland", 0, +1),
    ("Western Desert", 26.0, 27.5, "stable desert", 0, +1),
]


def series(start: float, slope_per_year: float, rng: random.Random, cp: int | None) -> list[dict]:
    out = []
    for k, year in enumerate(range(2003, 2026)):
        active = cp is None or year >= cp
        v = start + (slope_per_year * (year - (cp or 2003)) if active else 0) + rng.gauss(0, abs(start) * 0.03 + 0.01)
        out.append({"t": str(year), "v": round(v, 4)})
    return out


def item(i: int, area, var: dict, rng: random.Random) -> dict:
    name, lat, lon, fp, ndvi_sign, lst_sign = area
    sign = {"NDVI": ndvi_sign, "LST_DAY": lst_sign, "T2M": 1}[var["code"]]
    base = {"NDVI": 0.08 if "desert" in fp or fp == "new farmland" else 0.5, "LST_DAY": 40.0, "T2M": 24.0}[var["code"]]
    mag = {"NDVI": 0.02, "LST_DAY": 0.08, "T2M": 0.025}[var["code"]]
    cp = rng.choice([2008, 2012, 2016, 2019]) if sign != 0 and var["code"] != "T2M" else None
    p = round(rng.uniform(0.0001, 0.01), 4) if sign else round(rng.uniform(0.1, 0.9), 3)
    q = min(1.0, round(p * 3, 4))
    slope = round(sign * mag * 10 * rng.uniform(0.6, 1.4), 3) if sign else round(rng.uniform(-0.002, 0.002), 4)
    direction = "increasing" if sign > 0 else "decreasing" if sign < 0 else "no clear trend"
    jlat, jlon = lat + rng.uniform(-0.15, 0.15), lon + rng.uniform(-0.15, 0.15)
    return {
        "id": f"{var['code'].lower()}-{i:03d}",
        "location": {"frame": "earth", "lat": round(jlat, 4), "lon": round(jlon, 4), "name": name},
        "time": "2003-2025",
        "score": round(1 - q, 4),
        "label": direction,
        "variable": var,
        "trend": {
            "period": "2003-2025", "slope_per_decade": slope, "p": p, "q": q,
            "significant": q < 0.05, "direction": direction,
            "method": "Mann-Kendall (Yue-Wang variance correction) + Sen's slope, BH-FDR",
            "change_point_year": cp, "p_plain_mk": round(p / 2, 5),
        },
        "fingerprint": fp,
        "sentence": f"FAKE DATA. {var['name']} {direction} by {slope:+} {var['unit']}/decade near {name}.",
        "explanation": [
            {"feature": "NDVI slope", "contribution": round(ndvi_sign * rng.uniform(0.5, 1), 3)},
            {"feature": "LST slope", "contribution": round(lst_sign * rng.uniform(0.5, 1), 3)},
            {"feature": "change point year", "contribution": round(rng.uniform(-0.3, 0.3), 3)},
        ],
        "series": series(base, slope / 10, rng, cp),
    }


def main(seed: int = 7) -> None:
    rng = random.Random(seed)
    items, i = [], 0
    for var in VARIABLES:
        for area in AREAS:
            for _ in range(4):
                items.append(item(i, area, var, rng))
                i += 1
    bundle = {
        "version": "0.2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "challenge": "Egypt Trend Detective (FAKE DATA)",
        "model": {"name": "mock-trend-engine", "version": "0.0",
                  "metrics": {"false_alarm_rate": 0.0, "gistemp_slope_error": 0.0},
                  "notes": "Fixture data, not real results."},
        "items": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, indent=2))
    print(f"wrote {OUT} with {len(items)} items")


if __name__ == "__main__":
    main()
