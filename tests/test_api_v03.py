"""v0.3 endpoints in MOCK mode must return shapes that match contracts/trend.schema.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts" / "trend.schema.json").read_text(encoding="utf-8"))
EGYPT = {"south": 22.0, "north": 31.7, "west": 24.7, "east": 36.9, "name": "Egypt"}
KENYA = {"south": -4.7, "north": 5.0, "west": 33.9, "east": 41.9, "name": "Kenya"}


def validate(obj: dict, def_name: str) -> None:
    jsonschema.validate(obj, {"$ref": f"#/$defs/{def_name}", **{k: v for k, v in SCHEMA.items() if k != "title"}})


@pytest.fixture()
def client():
    os.environ["MOCK"] = "1"
    from api.main import app
    return TestClient(app)


def test_variables_and_regions(client):
    validate(client.get("/api/variables").json(), "VariableList")
    validate(client.get("/api/regions").json(), "RegionList")


def test_point_trend(client):
    r = client.get("/api/trend/point", params={"lat": 30.04, "lon": 31.24, "var": "T2M"})
    assert r.status_code == 200
    validate(r.json(), "TrendResult")


@pytest.mark.parametrize("box", [EGYPT, KENYA])
def test_region_trend_any_country(client, box):
    r = client.get("/api/trend/region", params={**box, "var": "T2M"})
    assert r.status_code == 200
    g = r.json()
    validate(g, "GridTrend")
    gr = g["grid"]
    assert box["south"] <= gr["lat0"] and gr["lat0"] + (gr["nrows"] - 1) * gr["dlat"] <= box["north"]


def test_world_trend(client):
    r = client.get("/api/trend/world", params={"var": "T2M"})
    assert r.status_code == 200
    validate(r.json(), "GridTrend")


def test_errors(client):
    assert client.get("/api/trend/point", params={"lat": 0, "lon": 0, "var": "NOPE"}).status_code == 404
    assert client.get("/api/trend/point", params={"lat": 120, "lon": 0}).status_code == 422
    assert client.get("/api/trend/region", params={"south": 10, "north": 5, "west": 0, "east": 1}).status_code == 422
    russia = {"south": 41, "north": 82, "west": -180, "east": 180}
    assert client.get("/api/trend/region", params=russia).status_code == 413
    assert client.get("/api/trend/world", params={"var": "RH2M"}).status_code == 404
    assert client.get("/api/trend/cell", params={"lat": 30, "lon": 31.25}).status_code == 404
