"""The farming outlook checker (ml/check_farming.py): the file in the repo passes, a small model file
passes with notes, and files that would show wrong numbers or break the app are caught."""
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


def minimal(o: dict) -> dict:
    """The smallest file a trained model may write: 2 crops, irrigated only, one year, nothing optional."""
    crops = [{"id": "maize", "name": "Maize"}, {"id": "rice", "name": "Rice"}]
    return {
        "version": "0.4", "region": o["region"], "grid": o["grid"], "method": "Test model.",
        "horizons": [2025], "inside": o["inside"], "crops": crops,
        "suitability": {"irrigated": {c["id"]: [o["suitability"]["irrigated"][c["id"]][0]] for c in crops}},
    }


def test_the_outlook_in_the_repo_passes(outlook):
    errors, notes = check_farming.problems(outlook)
    assert errors == [] and notes == []
    fixture = json.loads((ROOT / "contracts" / "fixtures" / "farming_EGY.json").read_text(encoding="utf-8"))
    assert check_farming.problems(fixture)[0] == []


def test_a_small_model_file_passes_with_notes(outlook):
    errors, notes = check_farming.problems(minimal(outlook))
    assert errors == []
    text = " ".join(notes)
    for part in ("rainfed", "years_to_heat_limit", "one year", "temp_now_c", "source", "apple"):
        assert part in text


def _short_grid(o):
    o["suitability"]["irrigated"]["wheat"][0] = o["suitability"]["irrigated"]["wheat"][0][:-1]


def _crop_without_scores(o):
    del o["suitability"]["irrigated"]["wheat"]


def _decimal_scores(o):
    o["suitability"]["irrigated"]["wheat"][0][0] = 55.5


def _score_over_100(o):
    o["suitability"]["irrigated"]["wheat"][0][0] = 140


def _missing_horizon_grid(o):
    o["suitability"]["rainfed"]["wheat"] = o["suitability"]["rainfed"]["wheat"][:2]


def _no_scores_at_all(o):
    o["suitability"] = {}


def _wrong_inside_length(o):
    o["inside"] = o["inside"][:-3]


def _nothing_inside(o):
    o["inside"] = "0" * len(o["inside"])


def _short_heat_grid(o):
    o["years_to_heat_limit"]["wheat"] = o["years_to_heat_limit"]["wheat"][:10]


def _no_method(o):
    del o["method"]


@pytest.mark.parametrize("change", [
    _short_grid, _crop_without_scores, _decimal_scores, _score_over_100, _missing_horizon_grid, _no_scores_at_all,
    _wrong_inside_length, _nothing_inside, _short_heat_grid, _no_method,
])
def test_broken_outlooks_are_caught(outlook, change):
    broken = copy.deepcopy(outlook)
    change(broken)
    errors, _ = check_farming.problems(broken)
    assert errors, "this file would break the app or show wrong numbers and must be reported"


def test_command_line(tmp_path, outlook, capsys):
    assert check_farming.main([]) == 0
    bad = copy.deepcopy(outlook)
    _short_grid(bad)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    assert check_farming.main([str(path)]) == 1
    assert "suitability.irrigated.wheat" in capsys.readouterr().out
    assert check_farming.main([str(tmp_path / "missing.json")]) == 1
