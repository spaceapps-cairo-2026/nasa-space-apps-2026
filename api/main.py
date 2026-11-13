"""Lane B: API that serves the PredictionBundle and the static app.

Run:  MOCK=1 uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "fixtures" / "sample_predictions.json"
REAL = ROOT / "ml" / "outputs" / "predictions.json"
API_VERSION = "0.3"


def is_mock() -> bool:
    return os.getenv("MOCK", "1") == "1" or not REAL.exists()


@lru_cache(maxsize=16)
def _load(path: str, mtime: float) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def bundle() -> dict:
    path = FIXTURE if is_mock() else REAL
    return _load(str(path), path.stat().st_mtime)


app = FastAPI(title="Space Apps 2026", version=API_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mock": is_mock(), "version": API_VERSION}


@app.get("/api/meta")
def meta() -> dict:
    b = bundle()
    return {"challenge": b["challenge"], "model": b["model"], "version": b["version"]}


@app.get("/api/predictions")
def predictions(min_score: float = 0.0, label: str | None = None) -> dict:
    b = bundle()
    items = [
        it for it in b["items"]
        if it["score"] >= min_score and (label is None or it["label"] == label)
    ]
    return {**b, "items": items}


@app.get("/api/items/{item_id}")
def item(item_id: str) -> dict:
    for it in bundle()["items"]:
        if it["id"] == item_id:
            return it
    raise HTTPException(status_code=404, detail="item not found")


# ---------------------------------------------------------------------------
# v0.3 F1 trend explorer (contracts/api.md). MOCK=1 answers from contracts/fixtures;
# MOCK=0 calls lane A's engine (ml.trends) once it provides point_trend & co.
# ---------------------------------------------------------------------------
FIXTURES = ROOT / "contracts" / "fixtures"
MOCK_NOTE = "Sample data: the live trend engine is not connected yet."
MAX_BOX_SQ_DEG = 2500  # bigger boxes would need too many live NASA tiles


def _fixture(name: str) -> dict:
    return _load(str(FIXTURES / name), (FIXTURES / name).stat().st_mtime)


def _engine():
    if os.getenv("MOCK", "1") == "1":
        return None
    try:
        import ml.trends as engine  # lane A
    except Exception:
        return None
    return engine if hasattr(engine, "point_trend") else None


def _known_var(var: str) -> None:
    eng = _engine()
    codes = {v["code"] for v in (eng.VARIABLES if eng else _fixture("variables.json")["variables"])}
    if var not in codes:
        raise HTTPException(status_code=404, detail=f"Unknown measurement {var}.")


def _call(fn, *args):
    try:
        return fn(*args)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'"))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _crop_grid(g: dict, south: float, north: float, west: float, east: float, name: str | None) -> dict | None:
    """Cut a GridTrend down to the cells whose centers fall inside the box (mock mode only)."""
    gr = g["grid"]
    rows = [i for i in range(gr["nrows"]) if south <= gr["lat0"] + i * gr["dlat"] <= north]
    cols = [j for j in range(gr["ncols"]) if west <= gr["lon0"] + j * gr["dlon"] <= east]
    if not rows or not cols:
        return None
    idx = [i * gr["ncols"] + j for i in rows for j in cols]
    slope = [g["slope_per_decade"][k] for k in idx]
    conf = "".join(g["confidence"][k] for k in idx)
    proven = [(s, c) for s, c in zip(slope, conf) if c in "SM" and s is not None]
    vals = sorted(s for s in slope if s is not None)
    return {
        **g,
        "region": {"id": "box", "name": name, "bbox": [west, south, east, north], "n_cells": sum(c != "-" for c in conf)},
        "grid": {**gr, "lat0": gr["lat0"] + rows[0] * gr["dlat"], "lon0": gr["lon0"] + cols[0] * gr["dlon"],
                 "nrows": len(rows), "ncols": len(cols)},
        "slope_per_decade": slope, "q": [g["q"][k] for k in idx], "confidence": conf,
        "summary": {"n_cells": sum(c != "-" for c in conf), "n_increasing": sum(s > 0 for s, _ in proven),
                    "n_decreasing": sum(s < 0 for s, _ in proven), "n_not_proven": conf.count("N"),
                    "median_slope_per_decade": vals[len(vals) // 2] if vals else None},
        "mock": True,
    }


@app.get("/api/variables")
def variables() -> dict:
    eng = _engine()
    return {"version": "0.3", "variables": eng.VARIABLES} if eng else _fixture("variables.json")


@app.get("/api/regions")
def regions() -> dict:
    eng = _engine()
    return {"version": "0.3", "regions": eng.REGIONS} if eng else _fixture("regions.json")


@app.get("/api/trend/point")
def trend_point(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    var: str = "T2M",
    name: str | None = None,
) -> dict:
    _known_var(var)
    eng = _engine()
    if eng:
        return _call(eng.point_trend, lat, lon, var, name)
    if var != "T2M":
        raise HTTPException(status_code=404, detail=f"No sample data for this measurement yet. {MOCK_NOTE}")
    return {**_fixture("trend_point_cairo_T2M.json"), "mock": True, "mock_note": MOCK_NOTE + " Showing Cairo for every point."}


@app.get("/api/trend/region")
def trend_region(
    south: float = Query(..., ge=-90, le=90),
    north: float = Query(..., ge=-90, le=90),
    west: float = Query(..., ge=-180, le=180),
    east: float = Query(..., ge=-180, le=180),
    var: str = "T2M",
    name: str | None = None,
) -> dict:
    _known_var(var)
    if south >= north or west >= east:
        raise HTTPException(status_code=422, detail="The box must have south < north and west < east.")
    if (north - south) * (east - west) > MAX_BOX_SQ_DEG:
        raise HTTPException(status_code=413, detail="This area is too large to fetch live. Zoom out to see the world map, "
                                                    "or click points inside it.")
    eng = _engine()
    if eng:
        return _call(eng.region_trend, var, south, north, west, east, name)
    if var != "T2M":
        raise HTTPException(status_code=404, detail=f"No sample map for this measurement yet. {MOCK_NOTE}")
    egypt = _fixture("trend_region_egypt_T2M.json")
    w, s, e, n = egypt["region"]["bbox"]
    inside_egypt = west >= w - 1 and east <= e + 1 and south >= s - 1 and north <= n + 1
    out = _crop_grid(egypt if inside_egypt else _fixture("trend_world_T2M.json"), south, north, west, east, name)
    if out is None:
        raise HTTPException(status_code=404, detail="No grid cells inside this area.")
    return out


@app.get("/api/trend/world")
def trend_world(var: str = "T2M") -> dict:
    _known_var(var)
    eng = _engine()
    if eng and hasattr(eng, "world_trend"):
        return _call(eng.world_trend, var)
    if var != "T2M":
        raise HTTPException(status_code=404, detail="The world map is only available for air temperature so far.")
    return {**_fixture("trend_world_T2M.json"), "mock": True}


@app.get("/api/trend/cell")
def trend_cell(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    var: str = "T2M",
) -> dict:
    _known_var(var)
    eng = _engine()
    if eng and hasattr(eng, "cell_trend"):
        return _call(eng.cell_trend, var, lat, lon)
    raise HTTPException(status_code=404, detail=f"The cell's chart needs the live engine. {MOCK_NOTE}")


# Static app last, so /api routes win.
app.mount("/", StaticFiles(directory=ROOT / "app", html=True), name="app")
