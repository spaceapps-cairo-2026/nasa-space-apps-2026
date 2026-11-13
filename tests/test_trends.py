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
    r = live.point_trend("GWETROOT", 32.0, 30.0)          # Mediterranean cell
    validate(r)
    if r["trend"]["level"] == -1:
        assert r["trend"]["direction"] == "no data" and "not enough" in r["sentence"]


def test_bad_requests():
    with pytest.raises(live.BadRequest):
        live.point_trend("NOPE", 30, 31)
    with pytest.raises(live.BadRequest):
        live.region_trend("T2M", 32, 22, 25, 35)
    with pytest.raises(live.BadRequest):
        live.region_trend("T2M_MIN", 22, 32, 25, 35)


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
    os.environ["MOCK"] = "1"
