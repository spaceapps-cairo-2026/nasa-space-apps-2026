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


@lru_cache(maxsize=1)
def _load(path: str, mtime: float) -> dict:
    return json.loads(Path(path).read_text())


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
# v0.3 F1 trend explorer (contracts/api.md). MOCK=1 serves contracts/fixtures;
# MOCK=0 calls lane A's engine (ml.trends) once it provides point_trend & co.
# ---------------------------------------------------------------------------
FIXTURES = ROOT / "contracts" / "fixtures"
MOCK_NOTE = "Sample data: the live trend engine is not connected yet."


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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
        raise HTTPException(status_code=404, detail=f"unknown variable {var}")


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
        try:
            return eng.point_trend(lat, lon, var, name)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
    if var != "T2M":
        raise HTTPException(status_code=404, detail=f"No sample data for {var} yet. {MOCK_NOTE}")
    return {**_fixture("trend_point_cairo_T2M.json"), "mock": True, "mock_note": MOCK_NOTE + " Showing Cairo for every point."}


@app.get("/api/trend/region")
def trend_region(region: str = "egypt", var: str = "T2M") -> dict:
    _known_var(var)
    eng = _engine()
    if eng:
        try:
            return eng.region_trend(region, var)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
    if region != "egypt" or var != "T2M":
        raise HTTPException(status_code=404, detail=f"No sample map for {region} {var} yet. {MOCK_NOTE}")
    return {**_fixture("trend_region_egypt_T2M.json"), "mock": True}


@app.get("/api/trend/cell")
def trend_cell(region: str, cell: str, var: str = "T2M") -> dict:
    _known_var(var)
    eng = _engine()
    if eng:
        try:
            return eng.cell_trend(region, cell, var)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
    raise HTTPException(status_code=404, detail=f"Cell time series needs the live engine. {MOCK_NOTE}")


# Static app last, so /api routes win.
app.mount("/", StaticFiles(directory=ROOT / "app", html=True), name="app")
