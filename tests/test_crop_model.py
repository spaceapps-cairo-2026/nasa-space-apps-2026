"""The trained crop model (ml/crop_model/) and its bridge to the app (ml/crop_outlook.py).

The expected Cairo numbers are the ones train_v3.py's model gave when it was deployed (ml/crop_model/README.md),
so a changed model file, a changed engine or changed NASA data in the repo is noticed here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
import crop_outlook as co  # noqa: E402

CAIRO = (30.0, 31.25)      # the grid cell that holds Cairo


@pytest.fixture(scope="module")
def engine():
    return co.load_engine()


@pytest.fixture(scope="module")
def cubes() -> dict:
    return {v: co.fao.monthly_cube(v) for v in co.ce.POWER_PARAMS}


@pytest.fixture(scope="module")
def cairo_report(engine, cubes) -> dict:
    lats, lons, _ = cubes["T2M"]
    i, j = int(np.argmin(abs(lats - CAIRO[0]))), int(np.argmin(abs(lons - CAIRO[1])))
    parameter = co.cell_parameters({v: c[2] for v, c in cubes.items()}, i, j)
    return co.ce.point_report(engine, *CAIRO, parameter=parameter, base_year=co.BASE_YEAR, horizons=co.HORIZONS, n_boot=10)


def test_model_file_loads(engine):
    assert engine.version == "crop-suitability-v3.1"
    assert engine.n_crops == 40 and set(engine.modes) == {"irrigated", "rainfed"}
    assert {"wheat", "rice", "maize", "sugarcane", "citrus", "tomato"} <= set(engine.crops)


def test_cairo_matches_the_deployed_model(cairo_report):
    irrigated = cairo_report["modes"]["irrigated"]
    top = [(r["crop"], r["suitability"]) for r in irrigated["ranking"]["now"][:3]]
    assert top == [("wheat", 0.972), ("vegetables", 0.942), ("onion", 0.94)]
    assert irrigated["viability"]["n_suitable_now"] == 19
    assert cairo_report["modes"]["rainfed"]["viability"]["n_suitable_now"] == 0
    assert cairo_report["period"] == {"start": 2001, "end": 2025, "base_year": 2025, "horizons": [5, 10]}


def test_rain_caution_travels_with_the_report(cairo_report):
    """Inside Egypt the model file flags the 2015 jump in the NASA POWER rain record."""
    assert cairo_report["data_quality_notes"]
    assert "data_quality_note" in cairo_report["features"]["rain_annual"]


def test_scores_stay_between_0_and_1_and_irrigation_matters(engine):
    desert = {"t_mean": 24.0, "t_coldest": 13.0, "t_warmest": 32.0, "tmax_hottest": 42.0, "rain_annual": 5.0,
              "rain_wettest3_share": 1.0, "rh_mean": 30.0, "soil_top_wetness": 0.06, "soil_root_wetness": 0.25,
              "soil_root_wetness_min": 0.25}
    row = np.array([[desert[k] for k in co.ce.FEATURES]])
    wet, dry = engine.suitability(row, "irrigated")[0], engine.suitability(row, "rainfed")[0]
    assert ((wet >= 0) & (wet <= 1) & (dry >= 0) & (dry <= 1)).all()
    assert (dry < 0.5).all(), "nothing fits a 5 mm desert on rain alone"
    assert (wet >= 0.5).sum() >= 5, "with water, several crops fit a hot desert climate"


def test_app_file_is_the_models_answer(cairo_report):
    """ml/outputs/farming_EGY.json holds the engine's scores, as whole numbers 0 to 100."""
    o = json.loads(co.OUT.read_text(encoding="utf-8"))
    g = o["grid"]
    k = round((CAIRO[0] - g["lat0"]) / g["dlat"]) * g["ncols"] + round((CAIRO[1] - g["lon0"]) / g["dlon"])
    assert o["horizons"] == [2025, 2030, 2035] and o["model"]["id"] == "crop-suitability-v3.1"
    for mode in co.MODES:
        for name, crop in cairo_report["modes"][mode]["crops"].items():
            grids = o["suitability"][mode][co.crop_id(name)]
            expected = [crop["now"], crop["plus5"]["point"], crop["plus10"]["point"]]
            assert all(abs(grids[h][k] - 100 * expected[h]) <= 0.51 for h in range(3)), (mode, name)
            low, high = o["suitability_10_low"][mode][co.crop_id(name)][k], o["suitability_10_high"][mode][co.crop_id(name)][k]
            assert low <= grids[2][k] <= high
    assert o["farmland"][k] == "1" and o["inside"][k] == "1"


def test_rain_gate_only_touches_rain_only_mode(engine):
    """v3 rule: rain-only scores fade to 0 below 100 mm a year (full at 200 mm for wheat and barley, 250 for others);
    irrigated scores are never changed."""
    assert engine.rain_gate is not None
    base = {"t_mean": 17.0, "t_coldest": 9.0, "t_warmest": 26.0, "tmax_hottest": 33.0, "rain_annual": 0.0,
            "rain_wettest3_share": 0.6, "rh_mean": 65.0, "soil_top_wetness": 0.3, "soil_root_wetness": 0.35,
            "soil_root_wetness_min": 0.25}
    rows = []
    for rain in (50.0, 150.0, 225.0, 400.0):
        rows.append([{**base, "rain_annual": rain}[k] for k in co.ce.FEATURES])
    rows = np.array(rows)
    g = engine.gate_factor(rows[:, co.ce.FEATURES.index("rain_annual")])
    wheat, citrus = engine.crops.index("wheat"), engine.crops.index("citrus")
    assert g[0].max() == 0 and (g[3] == 1).all()
    assert g[1, wheat] == 0.5 and abs(g[1, citrus] - 1 / 3) < 1e-9
    assert g[2, wheat] == 1 and abs(g[2, citrus] - 125 / 150) < 1e-9
    assert (engine.suitability(rows[:1], "rainfed") == 0).all()
    raw = engine.modes["irrigated"]["pack"].predict(np.column_stack([co.ce.clip_features(rows), np.ones(len(rows))]))
    assert np.allclose(engine.suitability(rows, "irrigated"), np.clip(raw, 0, 1))


def test_no_rain_only_false_alarms_in_egypt():
    """The v2 model scored up to 8 crops >= 50 on rain alone in Egypt's north and on the Red Sea coast."""
    o = json.loads(co.OUT.read_text(encoding="utf-8"))
    s, ids = o["suitability"]["rainfed"], [c["id"] for c in o["crops"]]
    for k, inside in enumerate(o["inside"]):
        if inside != "1":
            continue
        fits = [c for c in ids if (s[c][0][k] or 0) >= 50]
        rain = o["rain_now_mm"][k] or 0
        if rain < 100:
            assert not fits, (k, rain, fits)
        else:
            assert set(fits) <= {"wheat", "barley"}, (k, rain, fits)


def _egypt_areas() -> tuple[dict, "object"]:
    import pandas as pd
    t = pd.read_parquet(co.TRAINING_TABLE)
    return json.loads(co.OUT.read_text(encoding="utf-8")), t[(t.country == "Egypt") & (t.TA_total >= co.FARMLAND_MIN_HA)]


def _cell(o: dict, lat: float, lon: float) -> int:
    g = o["grid"]
    return round((lat - g["lat0"]) / g["dlat"]) * g["ncols"] + round((lon - g["lon0"]) / g["dlon"])


CODES = {"wheat": "whea", "maize": "maiz", "rice": "rice", "vegetables": "vege", "potato": "pota", "citrus": "citr",
         "sugar_beet": "sugb", "tomato": "toma", "sugarcane": "sugc", "sorghum": "sorg", "onion": "onio", "cotton": "cott",
         "groundnut": "grou", "beans": "bean", "sesame": "sesa", "banana": "bana", "barley": "barl", "sweet_potato": "swpo",
         "tropical_fruit": "trof", "temperate_fruit": "temf", "cassava": "cass", "cocoa": "coco", "rubber": "rubb",
         "oil_palm": "oilp", "tea": "teas", "yams": "yams", "coconut": "cnut", "robusta_coffee": "rcof"}


def test_crops_egypt_grows_score_where_they_are_grown():
    """v3.1: every crop Egypt grows on 15,000 ha or more (MapSPAM 2020) scores 50+ where it is grown, irrigated, now
    (area weighted). v3 failed this for sweet potato (18), beans, sesame, banana, barley and groundnut."""
    o, eg = _egypt_areas()
    s = o["suitability"]["irrigated"]
    for crop, code in CODES.items():
        area = eg["TA_" + code]
        if area.sum() < 15000:
            continue
        pairs = [(s[crop][0][_cell(o, a, b)], w) for a, b, w in zip(eg.lat, eg.lon, area) if w > 0 and o["inside"][_cell(o, a, b)] == "1"]
        score = sum(v * w for v, w in pairs) / sum(w for _, w in pairs)
        assert score >= 50, (crop, round(score), round(area.sum()))


def test_crops_egypt_does_not_grow_stay_low():
    o, eg = _egypt_areas()
    s = o["suitability"]["irrigated"]
    for crop, code in CODES.items():
        if eg["TA_" + code].sum() < 1000:
            assert max(v or 0 for v in s[crop][0]) < 50, crop
