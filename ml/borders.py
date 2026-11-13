"""Lane A: which grid cells belong to a country.

ml/live.py uses this so that a country's trend map, its false discovery correction and its average
cover the country itself, not the rectangle around it (sea and neighbours left out).

Borders are Natural Earth (public domain), the same files the app draws:
app/data/regions/<ISO>.geojson when a detailed one exists, else app/data/borders_50m.geojson.
No extra library: a scanline point in polygon test on a small grid of sample points per cell.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DETAILED = ROOT / "app" / "data" / "regions"
WORLD = ROOT / "app" / "data" / "borders_50m.geojson"
MIN_SHARE = 0.08   # a cell counts when at least this share of it is inside (the app clips with the same rule)
SAMPLES = 8        # sample points per cell side (8 x 8 = 64 per cell)


class UnknownCountry(ValueError):
    """No border is stored for this ISO code."""


@lru_cache(maxsize=1)
def _world() -> dict[str, dict]:
    if not WORLD.exists():
        return {}
    features = json.loads(WORLD.read_text(encoding="utf-8"))["features"]
    return {f["properties"]["iso"]: f for f in features if f.get("geometry")}


@lru_cache(maxsize=64)
def country(iso: str) -> tuple[str, dict]:
    """(name, GeoJSON geometry) of a country by ISO 3 letter code, e.g. "EGY"."""
    iso = iso.strip().upper()
    detailed = DETAILED / f"{iso}.geojson"
    feature = json.loads(detailed.read_text(encoding="utf-8")) if iso.isalnum() and detailed.exists() else _world().get(iso)
    if not feature:
        raise UnknownCountry(iso)
    return feature["properties"].get("name", iso), feature["geometry"]


def _edges(geometry: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """All ring edges of a Polygon or MultiPolygon as arrays x1, y1, x2, y2 (holes included)."""
    polys = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    a, b = [], []
    for poly in polys:
        for ring in poly:
            pts = np.asarray(ring, dtype=np.float64)[:, :2]
            if len(pts) < 3:
                continue
            a.append(pts)
            b.append(np.roll(pts, -1, axis=0))
    p, q = np.concatenate(a), np.concatenate(b)
    return p[:, 0], p[:, 1], q[:, 0], q[:, 1]


def cell_share(lats, lons, lat_step: float, lon_step: float, geometry: dict, samples: int = SAMPLES) -> np.ndarray:
    """Share of each grid cell (0 to 1) that lies inside the geometry, shape [lat, lon].

    Cells are centered on lats x lons. Even-odd rule over all rings, so holes and islands work.
    """
    lats, lons = np.asarray(lats, dtype=np.float64), np.asarray(lons, dtype=np.float64)
    x1, y1, x2, y2 = _edges(geometry)
    offs = (np.arange(samples) + 0.5) / samples - 0.5
    ys = (lats[:, None] + offs[None, :] * lat_step).ravel()
    xs = (lons[:, None] + offs[None, :] * lon_step).ravel()
    inside = np.zeros((len(ys), len(xs)), dtype=bool)
    lo, hi = min(y1.min(), y2.min()), max(y1.max(), y2.max())
    for r, y in enumerate(ys):
        if y < lo or y > hi:
            continue
        cross = (y1 > y) != (y2 > y)
        if not cross.any():
            continue
        xc = np.sort(x1[cross] + (y - y1[cross]) * (x2[cross] - x1[cross]) / (y2[cross] - y1[cross]))
        inside[r] = np.searchsorted(xc, xs) % 2 == 1
    return inside.reshape(len(lats), samples, len(lons), samples).mean(axis=(1, 3))


def country_mask(iso: str, lats, lons, lat_step: float, lon_step: float) -> tuple[str, np.ndarray]:
    """(country name, boolean mask [lat, lon]): True where the cell touches the country."""
    name, geometry = country(iso)
    return name, cell_share(lats, lons, lat_step, lon_step, geometry) >= MIN_SHARE
