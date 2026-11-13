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


def test_region_trend(client):
    r = client.get("/api/trend/region", params={"region": "egypt", "var": "T2M"})
    assert r.status_code == 200
    validate(r.json(), "RegionTrend")


def test_errors_are_404_or_422(client):
    assert client.get("/api/trend/point", params={"lat": 0, "lon": 0, "var": "NOPE"}).status_code == 404
    assert client.get("/api/trend/point", params={"lat": 120, "lon": 0}).status_code == 422
    assert client.get("/api/trend/region", params={"region": "mars"}).status_code == 404
    assert client.get("/api/trend/cell", params={"region": "egypt", "cell": "x"}).status_code == 404
