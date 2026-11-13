"""The farming outlook checker (ml/check_farming.py): the file in the repo passes, broken files are caught.

Every broken case below is one that crashed the Crops, Farmland or Decisions tab when tried in the app.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
import check_farming  # noqa: E402


@pytest.fixture(scope="module")
def outlook() -> dict:
    return json.loads((ROOT / "ml" / "outputs" / "farming_EGY.json").read_text(encoding="utf-8"))


def test_the_outlook_in_the_repo_passes(outlook):
    errors, _ = check_farming.problems(outlook)
    assert errors == []
    fixture = json.loads((ROOT / "contracts" / "fixtures" / "farming_EGY.json").read_text(encoding="utf-8"))
    assert check_farming.problems(fixture)[0] == []


def _without(*keys):
    def change(o):
        for k in keys:
            del o[k]
    return change


def _no_rainfed(o):
    del o["suitability"]["rainfed"]


def _two_horizons(o):
    o["horizons"] = [2025, 2035]


def _short_grid(o):
    o["suitability"]["irrigated"]["wheat"][0] = o["suitability"]["irrigated"]["wheat"][0][:-1]


def _crop_without_scores(o):
    del o["suitability"]["irrigated"]["wheat"]


def _decimal_scores(o):
    o["suitability"]["irrigated"]["wheat"][0][0] = 55.5


def _null_trend_inside(o):
    o["temp_trend_per_decade"][o["inside"].index("1")] = None


@pytest.mark.parametrize("change", [
    _without("years_to_heat_limit"), _without("temp_now_c", "rain_now_mm"), _without("temp_trend_per_decade"),
    _no_rainfed, _two_horizons, _short_grid, _crop_without_scores, _decimal_scores, _null_trend_inside,
])
def test_broken_outlooks_are_caught(outlook, change):
    broken = copy.deepcopy(outlook)
    change(broken)
    errors, _ = check_farming.problems(broken)
    assert errors, "this file would crash a tab in the app and must be reported"


def test_missing_default_crop_is_a_warning(outlook):
    o = copy.deepcopy(outlook)
    o["crops"] = [c for c in o["crops"] if c["id"] != "apple"]
    errors, warnings = check_farming.problems(o)
    assert errors == [] and any("apple" in w for w in warnings)


def test_command_line(tmp_path, outlook, capsys):
    assert check_farming.main([]) == 0
    bad = copy.deepcopy(outlook)
    del bad["years_to_heat_limit"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    assert check_farming.main([str(path)]) == 1
    assert "years_to_heat_limit" in capsys.readouterr().out
    assert check_farming.main([str(tmp_path / "missing.json")]) == 1
