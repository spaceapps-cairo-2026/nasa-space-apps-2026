"""v0.3 F1 contract: every fixture must match its shape in contracts/trend.schema.json."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts" / "trend.schema.json").read_text(encoding="utf-8"))
FIX = ROOT / "contracts" / "fixtures"


def validate(obj: dict, def_name: str) -> None:
    schema = {"$ref": f"#/$defs/{def_name}", **{k: v for k, v in SCHEMA.items() if k != "title"}}
    jsonschema.validate(obj, schema)


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name,def_name",
    [
        ("variables.json", "VariableList"),
        ("regions.json", "RegionList"),
        ("trend_point_cairo_T2M.json", "TrendResult"),
        ("trend_region_egypt_T2M.json", "GridTrend"),
        ("trend_world_T2M.json", "GridTrend"),
    ],
)
def test_fixture_matches_schema(name: str, def_name: str) -> None:
    validate(load(name), def_name)


@pytest.mark.parametrize("name", ["trend_region_egypt_T2M.json", "trend_world_T2M.json"])
def test_grid_arrays_line_up(name: str) -> None:
    g = load(name)
    n = g["grid"]["nrows"] * g["grid"]["ncols"]
    assert len(g["slope_per_decade"]) == len(g["q"]) == len(g["confidence"]) == n
    for s, q, c in zip(g["slope_per_decade"], g["q"], g["confidence"]):
        assert (c == "-") == (s is None) == (q is None)


def test_grid_summary_adds_up() -> None:
    g = load("trend_region_egypt_T2M.json")
    s = g["summary"]
    assert s["n_increasing"] + s["n_decreasing"] + s["n_not_proven"] == s["n_cells"]
    assert s["n_not_proven"] == g["confidence"].count("N")


def test_world_grid_is_the_nasa_power_grid() -> None:
    gr = load("trend_world_T2M.json")["grid"]
    assert (gr["nrows"], gr["ncols"], gr["dlat"], gr["dlon"]) == (361, 576, 0.5, 0.625)
    assert (gr["lat0"], gr["lon0"]) == (-90.0, -180.0)


def test_wrong_shape_is_rejected() -> None:
    bad = load("trend_point_cairo_T2M.json")
    bad["trend"]["confidence"] = "87% true"
    with pytest.raises(jsonschema.ValidationError):
        validate(bad, "TrendResult")


def test_sentences_never_say_no_change() -> None:
    assert "no change" not in load("trend_point_cairo_T2M.json")["sentence"].lower()
