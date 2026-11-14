"""Trend engine and trend API tests. No internet needed: Egypt comes from the repo, the rest is mocked."""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import jsonschema
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
import live  # noqa: E402
import trends as T  # noqa: E402

SCHEMA = json.loads((ROOT / "contracts" / "trend.schema.json").read_text())
FIXTURES = ROOT / "contracts" / "fixtures"


def validate(answer: dict) -> None:
    jsonschema.validate(answer, SCHEMA)


# ---------- engine ----------

def test_known_slope_is_recovered():
    years = np.arange(25)
    rng = np.random.default_rng(0)
    x = 0.05 * years + rng.normal(0, 0.05, 25)           # true trend: +0.5 per decade
    res = T.trend_one(x)
    assert abs(res["slope"] - 0.5) < 0.05
    assert res["slope_lo"] < 0.5 < res["slope_hi"]
    assert res["p"] < 0.001


def test_matches_reference_library():
    pmk = pytest.importorskip("pymannkendall")
    rng = np.random.default_rng(1)
    x = rng.normal(size=(20, 25)) + np.linspace(0, 1, 25)
    ours = T.trend_grid(x, "mk")
    for k in range(len(x)):
        ref = pmk.original_test(x[k])
        assert abs(ref.p - ours["p"][k]) < 1e-9
        assert abs(ref.slope * 10 - ours["slope"][k]) < 1e-9


def test_false_alarm_rate_is_honest():
    """Trendless series, with and without autocorrelation: about 5% may be called significant."""
    rng = np.random.default_rng(2)
    for rho in (0.0, 0.4):
        x = np.zeros((4000, 75))
        noise = rng.normal(size=x.shape)
        for t in range(1, 75):
            x[:, t] = rho * x[:, t - 1] + noise[:, t]
        rate = np.mean(T.trend_grid(x[:, 50:])["p"] < 0.05)
        assert rate < 0.08, f"rho={rho}: {rate:.1%} false alarms"


def test_missing_data_gives_no_data_not_a_crash():
    x = np.full((3, 25), np.nan)
    x[1] = np.arange(25.0)
    x[2, :10] = 1.0                                       # only 10 valid years
    res = T.trend_grid(x)
    assert np.isnan(res["p"][0]) and np.isnan(res["p"][2]) and res["p"][1] < 0.001
    assert list(T.confidence_levels(T.fdr_bh(res["p"]))) == [-1, 2, -1]


def test_fdr_matches_statsmodels():
    multitest = pytest.importorskip("statsmodels.stats.multitest")
    p = np.random.default_rng(3).uniform(size=200) ** 2
    assert np.allclose(T.fdr_bh(p), multitest.multipletests(p, method="fdr_bh")[1])


def test_annual_means_need_nine_months():
    m = np.arange(24.0)
    m[12:16] = np.nan                                     # second year: only 8 valid months
    a = T.annual_means(m)
    assert a[0] == pytest.approx(5.5) and np.isnan(a[1])


def test_gistemp_rate_is_reproduced():
    """F5 validation: NASA's global warming rate 2003 to 2025 is about 0.27 to 0.28 C per decade."""
    with open(ROOT / "data" / "processed" / "gistemp_global_annual.csv") as f:
        rows = {int(r["year"]): float(r["anomaly_c"]) for r in csv.DictReader(f)}
    res = T.trend_one([rows[y] for y in range(2003, 2026)])
    assert 0.25 < res["slope"] < 0.31
    assert res["p"] < 0.01


def test_change_point_finds_a_step():
    x = np.r_[np.zeros(12), np.ones(13)] + np.random.default_rng(4).normal(0, 0.1, 25)
    cp = T.change_point(x, range(2001, 2026))
    assert cp and abs(cp["year"] - 2013) <= 1
    assert T.change_point(np.random.default_rng(5).normal(size=25), range(2001, 2026)) is None


# ---------- live layer on the Egypt grid (in the repo, no internet) ----------

def test_egypt_region_matches_contract():
    r = live.region_trend("T2M", 22, 32, 25, 35)
    validate(r)
    assert r["data_from"] == "repo" and r["summary"]["cells"] == 357
    g = r["grid"]
    assert len(g["slope_per_decade"]) == len(g["lats"]) and len(g["slope_per_decade"][0]) == len(g["lons"])
    assert r["seconds"] < 5
    assert "—" not in r["sentence"] + r["mean_sentence"]


def test_egypt_point_matches_contract():
    r = live.point_trend("T2M", 30.04, 31.24)
    validate(r)
    assert r["data_from"] == "repo" and len(r["series"]) == 25
    assert r["location"]["cell_lat"] == 30.0 and r["location"]["cell_lon"] == 31.25


def test_sea_cells_have_no_soil_wetness():
    """Over the sea NASA fills soil wetness with a constant 1: that is no data, never "not proven"."""
    for code in ("GWETROOT", "GWETTOP"):
        r = live.point_trend(code, 32.0, 30.0)            # Mediterranean cell
        validate(r)
        assert r["trend"]["level"] == -1 and r["trend"]["direction"] == "no data"
        assert "only on land" in r["sentence"] and "100%" not in r["sentence"]


def test_a_series_that_never_changes_is_no_data():
    res = T.trend_one(np.ones(25))
    assert res["slope"] is None and res["p"] is None
    assert T.trend_one(np.arange(25.0))["p"] < 0.01          # a real straight line still counts


def test_every_rain_answer_carries_the_2015_jump_caution():
    pt = live.point_trend("PRECTOTCORR", 30.04, 31.24)
    reg = live.region_trend("PRECTOTCORR", 22, 32, 25, 35, "EGY")
    for r in (pt, reg):
        validate(r)
        assert "2015" in r["caution"] and "rain gauges" in r["caution"]
    assert live.point_trend("T2M", 30.04, 31.24)["caution"] is None


def test_bad_requests():
    with pytest.raises(live.BadRequest):
        live.point_trend("NOPE", 30, 31)
    with pytest.raises(live.BadRequest):
        live.region_trend("T2M", 32, 22, 25, 35)
    with pytest.raises(live.BadRequest):
        live.region_trend("T2M_MIN", 22, 32, 25, 35)
    with pytest.raises(live.BadRequest):
        live.region_trend("T2M", 22, 32, 25, 35, country="XXX")     # no such country
    with pytest.raises(live.BadRequest):
        live.region_trend("T2M", 22, 32, 25, 35, country="FRA")     # France is not in this box


def test_error_messages_are_plain_sentences():
    """The app shows these as they are: no Python lists, no internal words."""
    for call in (lambda: live.region_trend("T2M_MIN", 22, 32, 25, 35), lambda: live.world_trend("T2M_MIN")):
        with pytest.raises(live.BadRequest) as exc:
            call()
        text = str(exc.value)
        assert "daily minimum air temperature" in text and text.endswith(".")
        assert "[" not in text and "grid" not in text and "—" not in text


def test_sentence_says_luck_as_a_percentage_and_keeps_the_sign_of_the_range():
    var = live.variable_info("RH2M")
    base = {"period": "2001-2025", "level_name": "moderate evidence", "change_point_year": None}
    # Range all on one side: sizes only.
    # The range is for the total change over the chosen years (24 years here: 2.4 x the per decade range).
    text = live.sentence(var, {**base, "level": 1, "slope_per_decade": 0.99, "slope_low": 0.05, "slope_high": 1.81, "p": 0.0265})
    assert "95% range 0.12 to 4.34" in text and "by luck only 2.6% of the time" in text and "p =" not in text
    assert "2.38 percentage points in total" in text and "0.99 percentage points per decade" in text
    # Range crossing zero (it happens for trends that are only just proven): the minus sign must stay.
    text = live.sentence(var, {**base, "level": 1, "slope_per_decade": 0.99, "slope_low": -0.05, "slope_high": 1.81, "p": 0.0478})
    assert "from -0.12 to +4.34" in text and "0.12 to 4.34)" not in text
    # Not proven: still a percentage, never "no change".
    text = live.sentence(var, {**base, "level": 0, "level_name": "not proven", "slope_per_decade": -0.16, "slope_low": -0.6, "slope_high": 0.2, "p": 0.441})
    assert "not proven" in text and "44% of the time" in text and "no change" not in text
    assert [live.luck_percent(p) for p in (0.0004, 0.00289, 0.0996, 1.0)] == ["less than 0.1%", "0.3%", "10%", "100%"]


def test_cell_share_of_a_simple_shape():
    import borders
    # A rectangle from 0 to 1 N and 0 to 0.9375 E: covers column 0, half of column 1, none of column 2.
    shape = {"type": "Polygon", "coordinates": [[[0, 0], [0.9375, 0], [0.9375, 1], [0, 1], [0, 0]]]}
    share = borders.cell_share([0.25, 0.75, 1.25], [0.3125, 0.9375, 1.5625], 0.5, 0.625, shape)
    assert np.allclose(share, [[1, 0.5, 0], [1, 0.5, 0], [0, 0, 0]])
    # A hole is not part of the shape.
    holed = {"type": "Polygon", "coordinates": [shape["coordinates"][0], [[0, 0], [0.625, 0], [0.625, 0.5], [0, 0.5], [0, 0]]]}
    assert borders.cell_share([0.25], [0.3125], 0.5, 0.625, holed)[0, 0] == 0


def test_country_map_covers_the_country_only():
    """With country=, sea and neighbours are no data and the counts, FDR and average use Egypt only."""
    box = live.region_trend("T2M", 22, 32, 25, 35)
    egy = live.region_trend("T2M", 22, 32, 25, 35, country="egy")
    validate(egy)
    assert box["country"] is None and egy["country"] == {"iso": "EGY", "name": "Egypt"}
    assert 300 < egy["summary"]["cells"] < box["summary"]["cells"] == 357
    assert egy["summary"]["with_data"] == egy["summary"]["cells"]
    g = egy["grid"]
    sea = (g["lats"].index(32.0), g["lons"].index(30.0))            # Mediterranean
    cairo = (g["lats"].index(30.0), g["lons"].index(31.25))
    assert g["level"][sea[0]][sea[1]] == -1 and g["slope_per_decade"][sea[0]][sea[1]] is None
    assert g["level"][cairo[0]][cairo[1]] >= 0
    assert box["grid"]["level"][sea[0]][sea[1]] >= 0                 # the box answer still has the sea cell
    assert "Egypt's" in egy["sentence"] and "across Egypt" in egy["mean_sentence"]
    assert "°C" in egy["mean_sentence"] and "averaged" not in egy["mean_sentence"]
    assert egy["summary"]["increasing"] <= box["summary"]["increasing"]


# ---------- API ----------

@pytest.mark.parametrize("name", ["trend_point.json", "trend_region.json", "trend_world.json"])
def test_fixtures_match_contract(name):
    validate(json.loads((FIXTURES / name).read_text()))


def test_api_mock(monkeypatch):
    monkeypatch.setenv("MOCK", "1")
    from api.main import app
    c = TestClient(app)
    validate(c.get("/api/trend/point?lat=1&lon=2").json())
    validate(c.get("/api/trend/region?lat_min=0&lat_max=5&lon_min=0&lon_max=5").json())
    validate(c.get("/api/trend/world").json())
    assert len(c.get("/api/variables").json()["variables"]) == 7
    assert c.get("/api/trend/point").status_code == 422


def test_api_real_on_egypt(monkeypatch):
    monkeypatch.setenv("MOCK", "0")
    from api.main import app
    c = TestClient(app)
    r = c.get("/api/trend/region?lat_min=22&lat_max=32&lon_min=25&lon_max=35&variable=GWETTOP")
    assert r.status_code == 200
    validate(r.json())
    r = c.get("/api/trend/point?lat=30.04&lon=31.24&variable=RH2M")
    assert r.status_code == 200 and r.json()["kind"] == "trend_point"
    assert c.get("/api/trend/point?lat=30&lon=31&variable=NOPE").status_code == 400
    assert c.get("/api/trend/region?lat_min=32&lat_max=22&lon_min=25&lon_max=35").status_code == 400
    r = c.get("/api/trend/region?lat_min=22&lat_max=32&lon_min=25&lon_max=35&variable=T2M&country=EGY")
    assert r.status_code == 200 and r.json()["country"]["name"] == "Egypt"
    validate(r.json())
    assert c.get("/api/trend/region?lat_min=22&lat_max=32&lon_min=25&lon_max=35&country=XXX").status_code == 400
    os.environ["MOCK"] = "1"


# ---------- user chosen year range (v0.5) ----------

def test_year_range_point():
    full = live.point_trend("T2M", 30.04, 31.24)
    part = live.point_trend("T2M", 30.04, 31.24, 2008, 2022)
    validate(part)
    t = part["trend"]
    assert (t["period"], t["start_year"], t["end_year"], t["n_years"]) == ("2008-2022", 2008, 2022, 15)
    assert len(part["series"]) == 25                                   # the chart keeps every year
    assert [p["t"] for p in part["trend_line"]] == [2008, 2022]        # the line covers the chosen years
    assert t["change_total"] == pytest.approx(t["slope_per_decade"] * 14 / 10, abs=1e-3)
    assert part["sentence"].startswith("From 2008 to 2022,") and "in total" in part["sentence"]
    f = full["trend"]
    assert (f["start_year"], f["end_year"]) == (2001, 2025) and full["sentence"].startswith("Since 2001,")
    assert f["change_total"] == pytest.approx(f["slope_per_decade"] * 2.4, abs=1e-3)
    # Same answer as running the engine on those years by hand.
    by_hand = T.trend_one([p["v"] for p in full["series"] if 2008 <= p["t"] <= 2022])
    assert t["slope_per_decade"] == pytest.approx(by_hand["slope"], abs=1e-4) and t["p"] == pytest.approx(by_hand["p"], abs=1e-5)


def test_year_range_region_and_limits():
    r = live.region_trend("T2M", 22, 32, 25, 35, "EGY", 2010, 2025)
    validate(r)
    assert (r["period"], r["start_year"], r["end_year"]) == ("2010-2025", 2010, 2025)
    assert r["mean_trend"]["period"] == "2010-2025" and len(r["mean_series"]) == 25
    assert r["sentence"].startswith("Since 2010,")
    assert r["summary"]["with_data"] == live.region_trend("T2M", 22, 32, 25, 35, "EGY")["summary"]["with_data"]
    for years in ((2020, 2025), (2015, 2005), (1990, 2020), (2010, 2030)):
        with pytest.raises(live.BadRequest) as exc:
            live.point_trend("T2M", 30, 31, *years)
        assert str(exc.value).endswith(".") and "[" not in str(exc.value)
    assert live.variables()["min_range_years"] == 10


def test_short_ranges_stay_honest():
    """10 trendless years, with and without autocorrelation: still about 5% false alarms."""
    rng = np.random.default_rng(6)
    for rho in (0.0, 0.3):
        x = np.zeros((4000, 60))
        noise = rng.normal(size=x.shape)
        for t in range(1, 60):
            x[:, t] = rho * x[:, t - 1] + noise[:, t]
        rate = np.mean(T.trend_grid(x[:, 50:])["p"] < 0.05)
        assert rate < 0.08, f"rho={rho}: {rate:.1%} false alarms"


def test_api_year_range(monkeypatch):
    monkeypatch.setenv("MOCK", "0")
    from api.main import app
    c = TestClient(app)
    r = c.get("/api/trend/point?lat=30.04&lon=31.24&start_year=2005&end_year=2020")
    assert r.status_code == 200 and r.json()["trend"]["period"] == "2005-2020"
    r = c.get("/api/trend/region?lat_min=22&lat_max=32&lon_min=25&lon_max=35&country=EGY&start_year=2005")
    assert r.status_code == 200 and r.json()["period"] == "2005-2025"
    assert c.get("/api/trend/point?lat=30&lon=31&start_year=2021").status_code == 400
    os.environ["MOCK"] = "1"


def test_box_smaller_than_one_cell_still_answers():
    """A small country (Luxembourg's box is 0.6 x 0.6 degrees) used to fail with 'smaller than one grid cell'.
    A valid box narrower than a cell is widened around its centre; an inverted box is still refused."""
    r = live.region_trend("T2M", 30.0, 30.1, 31.0, 31.1)          # inside Egypt, far below one cell
    assert r["summary"]["with_data"] >= 1 and len(r["grid"]["lats"]) >= 1 and len(r["grid"]["lons"]) >= 1
    with pytest.raises(live.BadRequest):
        live.region_trend("T2M", 30.1, 30.0, 31.0, 31.1)


def test_air_temperature_anywhere_needs_no_download():
    """v0.6: outside Egypt, air temperature comes from the committed world grid. Russia (68 NASA blocks, refused
    before on a laptop without the 131 MB cache) answers in about a second with no internet, and a point far from
    Egypt too. Egypt keeps its repo table."""
    rus = live.region_trend("T2M", 41.19, 81.25, -180.0, 180.0, country="RUS")
    assert rus["data_from"] == "world" and rus["summary"]["with_data"] > 9000
    pt = live.point_trend("T2M", 40.7, -74.0)
    assert pt["data_from"] == "world" and len(pt["series"]) == 25
    assert live.point_trend("T2M", 30.04, 31.24)["data_from"] == "repo"
    schema = json.loads((ROOT / "contracts" / "trend.schema.json").read_text(encoding="utf-8"))
    for answer in (rus, pt):
        jsonschema.validate(answer, schema)


def test_station_check_for_air_temperature_only():
    """v0.7: air temperature answers carry NASA GISTEMP (weather stations) for the same years; other measurements do not.
    Over Cairo the stations warm faster than POWER and prove it (ml/nasa_check.py)."""
    r = live.point_trend("T2M", 30.04, 31.24)
    sc = r["station_check"]
    assert sc and sc["start_year"] == 2001 and sc["end_year"] == 2025
    assert sc["level"] == 2 and sc["slope_per_decade"] > r["trend"]["slope_per_decade"] > 0
    assert live.point_trend("T2M", 30.04, 31.24, 2010, 2025)["station_check"]["end_year"] == 2025
    assert live.point_trend("RH2M", 30.04, 31.24)["station_check"] is None
    assert live.point_trend("T2M", 0.0, -30.0)["station_check"] is None      # mid Atlantic: no stations
