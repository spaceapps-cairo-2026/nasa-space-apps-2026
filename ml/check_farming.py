"""Lane A: check a farming outlook file before the app reads it.

    python run.py farming-check                 checks ml/outputs/farming_EGY.json
    python run.py farming-check my_model.json   checks any file

A trained crops / farmland model plugs into the Crops, Farmland and Decisions tabs by writing
ml/outputs/farming_EGY.json (format: contracts/farming.schema.json). This script says in plain words
what is wrong with a file, so problems show up here and not as a broken tab during the demo.
ERROR = the app would break or show wrong numbers. NOTE = it works; that part of the app is
hidden or looks different, so decide if that is what you want.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "farming.schema.json"
DEFAULT = ROOT / "ml" / "outputs" / "farming_EGY.json"
MODES = ("irrigated", "rainfed")


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _grid_errors(name: str, grid, n: int) -> list[str]:
    return [] if len(grid) == n else [f"{name}: has {len(grid)} values, the grid has {n} cells (nrows x ncols)"]


def problems(o: dict) -> tuple[list[str], list[str]]:
    """(errors, notes) for one farming outlook, in plain words."""
    errors: list[str] = []
    notes: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(o), key=lambda e: list(e.path)):
        where = ".".join(str(p) for p in e.path) or "the file"
        errors.append(f"{where}: {e.message[:200]}")
    if errors:
        return errors, notes                    # the checks below assume the basic shape is right

    n = o["grid"]["nrows"] * o["grid"]["ncols"]
    inside = [k for k, c in enumerate(o["inside"]) if c == "1"]
    if len(o["inside"]) != n:
        errors.append(f"inside: has {len(o['inside'])} characters, the grid has {n} cells (nrows x ncols)")
    elif not inside:
        errors.append("inside: no cell is marked 1, so the map would be empty")
    for name in ("evidence", "farmland", "outside_training"):
        if name in o and len(o[name]) != n:
            errors.append(f"{name}: has {len(o[name])} characters, the grid has {n} cells")
    for name in ("temp_now_c", "rain_now_mm", "temp_trend_per_decade", "rain_trend_mm_per_decade"):
        if name in o:
            errors += _grid_errors(name, o[name], n)

    ids = [c["id"] for c in o["crops"]]
    if len(set(ids)) != len(ids):
        errors.append("crops: two crops share the same id")
    n_h = len(o["horizons"])
    for mode, per_crop in o["suitability"].items():
        for cid in ids:
            grids = per_crop.get(cid)
            if grids is None:
                errors.append(f"suitability.{mode}: no scores for crop '{cid}' (every crop in 'crops' needs scores in every mode you send)")
            elif len(grids) != n_h:
                errors.append(f"suitability.{mode}.{cid}: has {len(grids)} grids, needs {n_h} (one per year in 'horizons')")
            else:
                for g in grids:
                    errors += _grid_errors(f"suitability.{mode}.{cid}", g, n)
        for extra in sorted(set(per_crop) - set(ids)):
            notes.append(f"suitability.{mode}.{extra}: scores for a crop that is not in 'crops', it will not be shown")
    for cid, grid in o.get("years_to_heat_limit", {}).items():
        errors += _grid_errors(f"years_to_heat_limit.{cid}", grid, n)
    for name in ("suitability_10_low", "suitability_10_high", "best_start_month"):
        for mode, per_crop in o.get(name, {}).items():
            for cid, grid in per_crop.items():
                errors += _grid_errors(f"{name}.{mode}.{cid}", grid, n)
    if errors:
        return sorted(set(errors)), notes

    for mode in MODES:
        if mode not in o["suitability"]:
            notes.append(f"no '{mode}' scores: that water button is switched off in the app")
            continue
        scored = [o["suitability"][mode][cid][0][k] for cid in ids for k in inside]
        if all(v is None for v in scored):
            notes.append(f"suitability.{mode}: every cell inside the country is null (shown as 0)")
        elif len({v for v in scored if v is not None}) == 1:
            notes.append(f"suitability.{mode}: every score is the same value, check the model's output scale (0 to 100)")
    heat = o.get("years_to_heat_limit", {})
    if not any(_is_number(v) for grid in heat.values() for v in grid):
        notes.append("no years_to_heat_limit: the 'Years to heat limit' view and that Decisions list are hidden")
    if n_h == 1:
        notes.append("only one year in 'horizons': the 'Change by' view is hidden and there is no future comparison")
    for name, what in (("temp_now_c", "average temperature"), ("rain_now_mm", "rain per year"),
                       ("temp_trend_per_decade", "warming trend"), ("evidence", "evidence badges")):
        if name not in o:
            notes.append(f"no {name}: the place panel does not show the {what}")
    if "source" not in o:
        notes.append("no 'source': the app shows no 'Source: ...' line for the scores")
    if "farmland" not in o:
        notes.append("no 'farmland': the place panel cannot say whether a place is farmed today")
    if not {"apple", "temperate_fruit"} & set(ids):
        notes.append("no crop with id 'apple' or 'temperate_fruit': the guided tour shows the first crop instead")
    return errors, notes


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else DEFAULT
    if not path.exists():
        print(f"ERROR  {path} does not exist")
        return 1
    try:
        outlook = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR  {path} is not valid JSON: {exc}")
        return 1
    errors, notes = problems(outlook)
    for e in errors:
        print("ERROR ", e)
    for w in notes:
        print("NOTE  ", w)
    if errors:
        print(f"\n{path}: {len(errors)} error(s). The app must not use this file yet.")
        return 1
    crops, cells = len(outlook["crops"]), outlook["inside"].count("1")
    print(f"OK  {path}: {crops} crops, {cells} cells inside {outlook['region']['name']}, years {outlook['horizons']}.")
    print(f"    method: {outlook['method'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
