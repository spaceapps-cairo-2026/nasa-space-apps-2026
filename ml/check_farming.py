"""Lane A: check a farming outlook file before the app reads it.

    python run.py farming-check                 checks ml/outputs/farming_EGY.json
    python run.py farming-check my_model.json   checks any file

A trained crops / farmland model plugs into the Crops, Farmland and Decisions tabs by writing
ml/outputs/farming_EGY.json (format: contracts/farming.schema.json). This script says in plain words
what is wrong with a file, so problems show up here and not as a broken tab during the demo.
ERROR = the app would break or show wrong numbers. WARNING = it works, but look at it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "farming.schema.json"
DEFAULT = ROOT / "ml" / "outputs" / "farming_EGY.json"
APP_HORIZONS = [2025, 2030, 2035]            # the labels of the app's Now / 2030 / 2035 buttons
APP_CROPS = {"wheat": "the crop the Crops tab opens with", "apple": "the crop the guided tour shows"}
MODES = ("irrigated", "rainfed")


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def problems(o: dict) -> tuple[list[str], list[str]]:
    """(errors, warnings) for one farming outlook, in plain words."""
    errors: list[str] = []
    warnings: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(o), key=lambda e: list(e.path)):
        where = ".".join(str(p) for p in e.path) or "the file"
        errors.append(f"{where}: {e.message[:200]}")
    if errors:
        return errors, warnings                 # the checks below assume the basic shape is right

    n = o["grid"]["nrows"] * o["grid"]["ncols"]
    inside = [k for k, c in enumerate(o["inside"]) if c == "1"]
    for name in ("inside", "evidence"):
        if len(o[name]) != n:
            errors.append(f"{name}: has {len(o[name])} characters, the grid has {n} cells (nrows x ncols)")
    for name in ("temp_now_c", "rain_now_mm", "temp_trend_per_decade"):
        if len(o[name]) != n:
            errors.append(f"{name}: has {len(o[name])} values, the grid has {n} cells")
        elif any(not _is_number(o[name][k]) for k in inside):
            errors.append(f"{name}: needs a number for every cell inside the country (found null)")
    if not inside:
        errors.append("inside: no cell is marked 1, so the map would be empty")

    ids = [c["id"] for c in o["crops"]]
    if len(set(ids)) != len(ids):
        errors.append("crops: two crops share the same id")
    n_h = len(o["horizons"])
    for cid in ids:
        for mode in MODES:
            grids = o["suitability"][mode].get(cid)
            if grids is None:
                errors.append(f"suitability.{mode}: no scores for crop '{cid}'")
            elif len(grids) != n_h:
                errors.append(f"suitability.{mode}.{cid}: has {len(grids)} grids, needs {n_h} (one per horizon)")
            elif any(len(g) != n for g in grids):
                errors.append(f"suitability.{mode}.{cid}: every grid needs {n} values (one per cell)")
        heat = o["years_to_heat_limit"].get(cid)
        if heat is None:
            errors.append(f"years_to_heat_limit: no list for crop '{cid}' (write null for every cell if the model has none)")
        elif len(heat) != n:
            errors.append(f"years_to_heat_limit.{cid}: has {len(heat)} values, needs {n}")
    for name in ("suitability_10_low", "suitability_10_high", "best_start_month"):
        for mode, per_crop in o.get(name, {}).items():
            for cid, grid in per_crop.items():
                if len(grid) != n:
                    errors.append(f"{name}.{mode}.{cid}: has {len(grid)} values, needs {n}")
    if errors:
        return errors, warnings

    if o["horizons"] != APP_HORIZONS:
        warnings.append(f"horizons are {o['horizons']}, but the app's buttons are labelled Now / 2030 / 2035")
    for cid, why in APP_CROPS.items():
        if cid not in ids:
            warnings.append(f"no crop with id '{cid}' ({why}); that view needs a lane B change before it works")
    for mode in MODES:
        scored = [o["suitability"][mode][cid][0][k] for cid in ids for k in inside]
        if all(v is None for v in scored):
            warnings.append(f"suitability.{mode}: every cell inside the country is null (shown as 0)")
        elif len({v for v in scored if v is not None}) == 1:
            warnings.append(f"suitability.{mode}: every score is the same value, check the model output scale (0 to 100)")
    return errors, warnings


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
    errors, warnings = problems(outlook)
    for e in errors:
        print("ERROR  ", e)
    for w in warnings:
        print("WARNING", w)
    if errors:
        print(f"\n{path}: {len(errors)} error(s). The app must not use this file yet.")
        return 1
    crops, cells = len(outlook["crops"]), outlook["inside"].count("1")
    print(f"OK  {path}: {crops} crops, {cells} cells inside {outlook['region']['name']}, horizons {outlook['horizons']}.")
    print(f"    method: {outlook['method'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
