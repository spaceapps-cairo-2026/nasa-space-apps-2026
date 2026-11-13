"""Lane B additions: /api/farming and /api/validation (trend endpoints are tested in tests/test_trends.py)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
FARMING_SCHEMA = json.loads((ROOT / "contracts" / "farming.schema.json").read_text(encoding="utf-8"))


@pytest.fixture()
def client():
    os.environ["MOCK"] = "1"
    from api.main import app
    return TestClient(app)


def test_farming_outlook(client):
    r = client.get("/api/farming", params={"country": "EGY"})
    assert r.status_code == 200
    f = r.json()
    jsonschema.validate(f, FARMING_SCHEMA)
    n = f["grid"]["nrows"] * f["grid"]["ncols"]
    assert len(f["inside"]) == len(f["evidence"]) == n
    for crop in f["crops"]:
        for grid in f["suitability"]["irrigated"][crop["id"]]:
            assert len(grid) == n
    assert client.get("/api/farming", params={"country": "KEN"}).status_code == 404


def test_farming_matches_known_geography(client):
    """Sanity: apples cannot survive Aswan's summer; rain-fed farming in Egypt is near impossible."""
    f = client.get("/api/farming", params={"country": "EGY"}).json()
    g = f["grid"]
    k = round((24.0 - g["lat0"]) / g["dlat"]) * g["ncols"] + round((32.5 - g["lon0"]) / g["dlon"])
    assert f["suitability"]["irrigated"]["apple"][0][k] == 0
    assert f["suitability"]["irrigated"]["date_palm"][0][k] >= 60
    assert max(v or 0 for v in f["suitability"]["rainfed"]["wheat"][0]) < 50


def test_validation(client):
    r = client.get("/api/validation")
    assert r.status_code == 200
    v = r.json()
    assert set(v["checks"]) >= {"cross_check", "false_alarms", "many_places", "farming"}
    assert all(c["passed"] for c in v["checks"]["farming"]["checks"])
    assert v["checks"]["false_alarms"]["false_alarm_rate"]["Egypt-like noise"] <= 0.075
    assert v["limitations"]
