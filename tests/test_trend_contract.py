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
        ("trend_region_egypt_T2M.json", "RegionTrend"),
    ],
)
def test_fixture_matches_schema(name: str, def_name: str) -> None:
    validate(load(name), def_name)


def test_region_summary_adds_up() -> None:
    r = load("trend_region_egypt_T2M.json")
    s = r["summary"]
    assert s["n_cells"] == len(r["cells"]) == r["region"]["n_cells"]
    assert s["n_increasing"] + s["n_decreasing"] + s["n_not_proven"] == s["n_cells"]


def test_not_proven_means_no_direction() -> None:
    for c in load("trend_region_egypt_T2M.json")["cells"]:
        assert (c["confidence"] == "not_proven") == (c["direction"] == "no_clear_trend")


def test_wrong_shape_is_rejected() -> None:
    bad = load("trend_point_cairo_T2M.json")
    bad["trend"]["confidence"] = "87% true"
    with pytest.raises(jsonschema.ValidationError):
        validate(bad, "TrendResult")


def test_sentences_never_say_no_change() -> None:
    assert "no change" not in load("trend_point_cairo_T2M.json")["sentence"].lower()
