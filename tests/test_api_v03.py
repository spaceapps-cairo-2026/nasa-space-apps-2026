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
    """Sanity of the trained crop model's outlook (ml/crop_outlook.py) against what is known about Egypt."""
    f = client.get("/api/farming", params={"country": "EGY"}).json()
    g = f["grid"]
    irr, rain = f["suitability"]["irrigated"], f["suitability"]["rainfed"]

    def at(lat: float, lon: float) -> int:
        return round((lat - g["lat0"]) / g["dlat"]) * g["ncols"] + round((lon - g["lon0"]) / g["dlon"])

    aswan, delta = at(24.0, 32.5), at(30.5, 31.25)
    assert irr["wheat"][0][delta] >= 80                                   # wheat is the Delta's winter crop
    assert max(irr[c][0][aswan] for c in ("cocoa", "oil_palm", "rubber")) < 10   # humid tropics crops, not Aswan
    assert irr["sugarcane"][0][aswan] >= 50                               # Upper Egypt is where sugarcane is grown
    assert all((rain[c["id"]][0][aswan] or 0) < 50 for c in f["crops"])   # nothing grows on rain alone in Aswan
    # The file comes from the model in ml/crop_model/, not from the FAO stand-in.
    assert f.get("model", {}).get("id") == "crop-suitability-v3" and len(f["crops"]) == 40


def test_validation(client):
    r = client.get("/api/validation")
    assert r.status_code == 200
    v = r.json()
    assert set(v["checks"]) >= {"cross_check", "false_alarms", "many_places", "farming"}
    assert all(c["passed"] for c in v["checks"]["farming"]["checks"])
    assert v["checks"]["false_alarms"]["false_alarm_rate"]["Egypt-like noise"] <= 0.075
    assert v["limitations"]
