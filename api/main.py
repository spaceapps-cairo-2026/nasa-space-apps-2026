"""Lane B: API that serves the PredictionBundle and the static app.

Run:  MOCK=1 uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "fixtures" / "sample_predictions.json"
REAL = ROOT / "ml" / "outputs" / "predictions.json"
API_VERSION = "0.2"


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


# Static app last, so /api routes win.
app.mount("/", StaticFiles(directory=ROOT / "app", html=True), name="app")
