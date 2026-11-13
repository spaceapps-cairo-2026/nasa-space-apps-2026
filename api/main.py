"""Lane B: API. Serves live trends (contracts/api.md v0.3), the old PredictionBundle and the static app.

Run:  python run.py mock   (fixtures, no internet needed)
      python run.py api    (real data: Egypt from the repo, the rest of the world live from NASA)
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
FIXTURES = ROOT / "contracts" / "fixtures"
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
    return {"status": "ok", "mock": os.getenv("MOCK", "1") == "1", "version": API_VERSION}


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


# ---------- live trends (F1) ----------

def _fixture(name: str) -> dict:
    path = FIXTURES / name
    return _load(str(path), path.stat().st_mtime)


def _live():
    """The trend engine is imported only when real data is asked for (mock mode never needs it)."""
    import sys
    if str(ROOT / "ml") not in sys.path:
        sys.path.insert(0, str(ROOT / "ml"))
    import live
    return live


def _call(fn, *args):
    live = _live()
    try:
        return fn(live)(*args)
    except live.BadRequest as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except live.RegionTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except live.SourceUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc))


def trend_mock() -> bool:
    """Trends are real unless MOCK=1 (they need no precomputed file, only the repo data or NASA)."""
    return os.getenv("MOCK", "1") == "1"


@app.get("/api/variables")
def variables() -> dict:
    if trend_mock():
        return _fixture("variables.json")
    return _call(lambda live: live.variables)


@app.get("/api/trend/point")
def trend_point(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
                variable: str = "T2M") -> dict:
    if trend_mock():
        return _fixture("trend_point.json")
    return _call(lambda live: live.point_trend, variable, lat, lon)


@app.get("/api/trend/region")
def trend_region(lat_min: float, lat_max: float, lon_min: float, lon_max: float,
                 variable: str = "T2M") -> dict:
    if trend_mock():
        return _fixture("trend_region.json")
    return _call(lambda live: live.region_trend, variable, lat_min, lat_max, lon_min, lon_max)


@app.get("/api/trend/world")
def trend_world(variable: str = "T2M", stride: int = 2) -> dict:
    if trend_mock():
        return _fixture("trend_world.json")
    return _call(lambda live: live.world_trend, variable, stride)


# ---------- farming outlook (F2 to F4) and validation (F5): lane B additions, lane A to review ----------

FARMING_COUNTRIES = {"EGY": "Egypt"}


def _first_existing(*paths: Path) -> dict | None:
    for path in paths:
        if path.exists():
            return _load(str(path), path.stat().st_mtime)
    return None


@app.get("/api/farming")
def farming(country: str = "EGY") -> dict:
    """Farming outlook for a focus country (python ml/farming.py), shape in contracts/farming.schema.json."""
    country = country.upper()
    if country not in FARMING_COUNTRIES:
        raise HTTPException(status_code=404, detail="Farming analysis is available for: " + ", ".join(FARMING_COUNTRIES.values()) + ".")
    out = _first_existing(ROOT / "ml" / "outputs" / f"farming_{country}.json", FIXTURES / f"farming_{country}.json")
    if out is None:
        raise HTTPException(status_code=404, detail="The farming outlook has not been computed yet (python ml/farming.py).")
    return out


@app.get("/api/validation")
def validation() -> dict:
    """Numbers for the app's 'How we know' panel (python ml/validate.py)."""
    out = _first_existing(ROOT / "ml" / "outputs" / "validation.json", FIXTURES / "validation.json")
    if out is None:
        raise HTTPException(status_code=404, detail="Validation has not been computed yet (python ml/validate.py).")
    return out


# Static app last, so /api routes win. The UI is dropped into app/; the API also runs without it.
if (ROOT / "app").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "app", html=True), name="app")
