"""Giovanni cross-check (ml/crosscheck.py) on files shaped like Giovanni's CSV download, made from our own data."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
import crosscheck as C  # noqa: E402

HEADER = ('Title:,"Time Series, Area-Averaged of {var} monthly"\n'
          "User Start Date:,2001-01-01T00:00:00Z\nUser End Date:,2025-12-31T23:59:59Z\n"
          "Bounding Box:,\"30.9375,29.75,31.5625,30.25\"\n"
          "Fill Value (mean_{var}):,-9999.9\n\n"
          "time,mean_{var}\n")


def write(path: Path, var: str, monthly: np.ndarray) -> None:
    rows = []
    for k, v in enumerate(monthly):
        y, m = 2001 + k // 12, k % 12 + 1
        rows.append(f"{y}-{m:02d}-01 00:00:00,{-9999.9 if not np.isfinite(v) else v:.6g}")
    path.write_text(HEADER.format(var=var) + "\n".join(rows) + "\n", encoding="utf-8")


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "FOLDER", tmp_path)
    return tmp_path


def test_reader_skips_metadata_and_fill_values(tmp_path):
    x = np.arange(300, dtype=float)
    x[5] = np.nan
    write(tmp_path / "a.csv", "M2TMNXSLV_5_12_4_T2M", x)
    got = C.read_giovanni_csv(tmp_path / "a.csv")
    assert len(got) == 299 and got["2001-01"] == 0 and "2001-06" not in got and got["2025-12"] == 299


def test_same_data_gives_the_same_answer_and_a_flat_satellite_shows_the_jump_is_not_real(folder):
    t2m = C.power_monthly("cairo", "T2M")
    write(folder / "cairo_merra2_t2m.csv", "M2TMNXSLV_5_12_4_T2M", t2m + 273.15)            # Kelvin, like Giovanni
    rain = C.power_monthly("cairo", "PRECTOTCORR")
    write(folder / "cairo_merra2_rain.csv", "M2TMNXFLX_5_12_4_PRECTOTCORR", rain / 86400)   # kg m-2 s-1
    early = np.nanmean(rain[:14 * 12])
    flat = np.full(300, early) * (1 + 0.2 * np.sin(np.arange(300)))                         # no jump
    write(folder / "cairo_imerg_rain.csv", "GPM_3IMERGM_07_precipitation", flat / 24)      # mm per hour
    (folder / "notes.csv").write_text("x", encoding="utf-8")                                # wrong name: skipped

    res = C.run()
    by = {r["source"]: r for r in res["rows"]}
    assert set(by) == {"merra2_t2m", "merra2_rain", "imerg_rain"}
    t = by["merra2_t2m"]
    assert t["year_to_year_correlation"] > 0.999 and abs(t["mean_difference"]) < 1e-3
    assert t["ours"]["per_decade"] == pytest.approx(t["giovanni"]["per_decade"], abs=1e-3)
    assert by["merra2_rain"]["giovanni"]["jump_ratio"] == pytest.approx(by["merra2_rain"]["ours"]["jump_ratio"], rel=1e-3)
    assert by["imerg_rain"]["giovanni"]["jump_ratio"] < 1.25 < 1.5 < by["imerg_rain"]["ours"]["jump_ratio"]
    assert "not in real rain" in res["rain_verdict"] and "inherits it from MERRA-2" in res["rain_verdict"]
    assert "Cairo" in res["plain"] and "—" not in res["plain"] + res["rain_verdict"]


def test_country_average_uses_the_border(folder):
    if C.live._missing_tiles("T2M", *C.AREAS["egypt"]["box"]):
        pytest.skip("Egypt's full box needs NASA tiles that are not cached on this computer (CI has no cache)")
    egy = C.power_monthly("egypt", "T2M")
    assert egy.shape == (300,) and np.isfinite(egy).all() and 15 < np.nanmean(egy) < 30
