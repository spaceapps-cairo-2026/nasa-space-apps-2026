"""Validation numbers for the Methods panel (F5). Lane B draft for lane A to review.

1. Cross-check against an independent NASA record: the global warming rate 2001 to 2025 from our
   NASA POWER world grid (area weighted) vs NASA GISTEMP (stations + ships, a different method).
2. False alarms: how often the trend test calls pure noise a trend (Egypt-like noise).
3. Many places at once: how many Egypt cells pass p < 0.05 vs after the FDR correction (q < 0.05).
4. Reality checks for the farming outlook.

Run:  python ml/validate.py   -> ml/outputs/validation.json and contracts/fixtures/validation.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
import trends  # noqa: E402  lane A's engine: the method chosen in decision D1

START, END = 2001, 2025
OUTS = [ROOT / "ml" / "outputs" / "validation.json", ROOT / "contracts" / "fixtures" / "validation.json"]
RNG = np.random.default_rng(15112026)
METHOD_NAME = "Sen's slope + Mann-Kendall with effective sample size correction (decision D1)"


def line_trend(y: np.ndarray) -> dict:
    """Our engine on one yearly series: rate per decade, its 95% range, p-value."""
    r = trends.trend_one(np.asarray(y, dtype=float))
    return {"per_decade": round(r["slope"], 3), "ci_low": round(r["slope_lo"], 3), "ci_high": round(r["slope_hi"], 3),
            "p": float(f"{r['p']:.2g}")}


def egypt_annual(var: str = "T2M") -> np.ndarray:
    """Egypt grid from the repo -> yearly means [cells, years] with the engine's own rule."""
    df = pd.read_parquet(ROOT / "data" / "processed" / "power_monthly.parquet")
    df = df[df["variable"] == var]
    wide = df.pivot_table(index="cell_id", columns="time", values="value")
    months = [f"{y}-{m:02d}" for y in range(START, END + 1) for m in range(1, 13)]
    return trends.annual_means(wide.reindex(columns=months).to_numpy(dtype=float))


def gistemp_check() -> dict:
    g = pd.read_csv(ROOT / "data" / "processed" / "gistemp_global_annual.csv")
    g = g[(g["year"] >= START) & (g["year"] <= END)]
    with np.load(ROOT / "data" / "processed" / "world" / "T2M_annual.npz") as z:
        lats, vals = z["lats"].astype(float), z["values"].astype(float)
    w = np.cos(np.radians(lats))[:, None] * np.ones(vals.shape[1])
    lat2d = lats[:, None] * np.ones(vals.shape[1])

    def area_mean_trend(mask: np.ndarray) -> dict:
        series = [float((vals[:, :, t][mask] * w[mask]).sum() / w[mask].sum()) for t in range(vals.shape[2])]
        return line_trend(np.array(series))

    full = np.isfinite(vals).all(-1)
    whole = area_mean_trend(full)
    no_antarctica = area_mean_trend(full & (lat2d > -60))
    arctic = area_mean_trend(full & (lat2d > 60))
    antarctica = area_mean_trend(full & (lat2d < -60))
    nasa = line_trend(g["anomaly_c"].to_numpy())
    overlap = lambda a, b: a["ci_low"] <= b["ci_high"] and b["ci_low"] <= a["ci_high"]
    agrees = overlap(no_antarctica, nasa)
    return {
        "title": "Cross-check with NASA's independent global record",
        "ours": {"label": "Our data (NASA POWER / MERRA-2), whole Earth, area weighted", **whole},
        "ours_no_antarctica": {"label": "Our data without Antarctica", **no_antarctica},
        "arctic": {"label": "Our data, Arctic only (north of 60 N)", **arctic},
        "antarctica": {"label": "Our data, Antarctica only (south of 60 S)", **antarctica},
        "reference": {"label": "NASA GISTEMP v4 (stations and ships, a different method)", **nasa},
        "period": [START, END], "agrees": bool(agrees),
        "plain": (f"From {START} to {END}, NASA's GISTEMP record warms the planet {nasa['per_decade']:+.2f} °C per decade. "
                  f"Our data gives {whole['per_decade']:+.2f} for the whole Earth, because it shows Antarctica cooling "
                  f"({antarctica['per_decade']:+.2f}); without Antarctica it gives {no_antarctica['per_decade']:+.2f}"
                  + (", and the two 95% ranges overlap. " if agrees else ", still lower than GISTEMP. ")
                  + f"Our data also shows the Arctic warming fastest ({arctic['per_decade']:+.2f} °C per decade), the pattern known as Arctic amplification. "
                  "The datasets measure slightly different things (air at 2 m vs surface and sea temperature), "
                  "so we show both numbers instead of hiding the gap."),
    }


def false_alarm_check(n_sim: int = 20000) -> dict:
    """Trendless series with Egypt-like noise and year-to-year resemblance; count 'trends' at p < 0.05."""
    ann = egypt_annual("T2M")
    t = np.arange(ann.shape[1])
    sds, rhos = [], []
    for row in ann:
        if np.isfinite(row).all():
            res = row - np.polyval(np.polyfit(t, row, 1), t)
            sds.append(res.std(ddof=2))
            rhos.append(np.corrcoef(res[:-1], res[1:])[0, 1])
    sd, rho = float(np.median(sds)), float(np.median(rhos))
    out = {}
    for label, r in (("Egypt-like noise", rho), ("strong year-to-year resemblance (0.5)", 0.5)):
        x = np.empty((n_sim, len(t)))
        x[:, 0] = RNG.normal(0, sd, n_sim)
        e = RNG.normal(0, sd * np.sqrt(1 - r ** 2), (n_sim, len(t)))
        for i in range(1, len(t)):
            x[:, i] = r * x[:, i - 1] + e[:, i]
        p = trends.trend_grid(x)["p"]
        out[label] = round(float(np.mean(p[np.isfinite(p)] < 0.05)), 3)
    return {
        "title": "How often the test cries wolf",
        "method": METHOD_NAME, "target": 0.05, "noise_sd_c": round(sd, 3), "year_to_year_resemblance": round(rho, 2),
        "false_alarm_rate": out, "simulations": n_sim, "d1_candidates": None,
        "plain": (f"We made {n_sim:,} fake 25-year series with Egypt's real noise and NO trend, and ran our real engine on them. "
                  f"It called {out['Egypt-like noise']:.1%} of them a trend (the target is about 5%). With strong year-to-year "
                  f"resemblance it called {out['strong year-to-year resemblance (0.5)']:.1%}. The team compared 7 methods on "
                  "20,000 series before choosing this one (decision D1)."),
    }


def fdr_check() -> dict:
    ann = egypt_annual("T2M")
    ps = trends.trend_grid(ann)["p"]
    ps = ps[np.isfinite(ps)]
    q = trends.fdr_bh(ps)
    expected_lucky = round(0.05 * len(ps))
    return {
        "title": "Testing many places at once",
        "cells": int(len(ps)), "p_below_0_05": int((ps < 0.05).sum()), "q_below_0_05": int((q < 0.05).sum()),
        "lucky_if_no_trend": expected_lucky,
        "plain": (f"Egypt has {len(ps)} grid cells. Testing each at p < 0.05 would show about {expected_lucky} 'trends' by pure luck "
                  f"even if nothing changed. Without correction {int((ps < 0.05).sum())} cells pass; after the false discovery "
                  f"rate correction {int((q < 0.05).sum())} remain, and those are the ones the map calls proven."),
    }


def farming_checks() -> dict:
    f = json.loads((ROOT / "ml" / "outputs" / "farming_EGY.json").read_text(encoding="utf-8"))
    g = f["grid"]

    def at(lat: float, lon: float) -> int:
        return round((lat - g["lat0"]) / g["dlat"]) * g["ncols"] + round((lon - g["lon0"]) / g["dlon"])

    aswan, delta = at(24.0, 32.5), at(30.5, 31.25)
    s = f["suitability"]
    checks = [
        ("Apples cannot survive Aswan's summer", s["irrigated"]["apple"][0][aswan] == 0, f"score {s['irrigated']['apple'][0][aswan]}"),
        ("Date palms do better in Aswan than in the Delta", s["irrigated"]["date_palm"][0][aswan] > s["irrigated"]["date_palm"][0][delta],
         f"{s['irrigated']['date_palm'][0][aswan]} vs {s['irrigated']['date_palm'][0][delta]}"),
        ("Wheat grows in the Delta's winter", s["irrigated"]["wheat"][0][delta] >= 80, f"score {s['irrigated']['wheat'][0][delta]}"),
        ("Rain alone cannot grow wheat anywhere in Egypt", max(v or 0 for v in s["rainfed"]["wheat"][0]) < 50,
         f"best rain-only score {max(v or 0 for v in s['rainfed']['wheat'][0])}"),
    ]
    return {"title": "Common-sense checks of the farming outlook",
            "checks": [{"check": c, "passed": bool(ok), "detail": d} for c, ok, d in checks]}


LIMITATIONS = [
    "Each grid cell is about 55 by 60 km: it describes a region, not one farm.",
    "NASA POWER is a model built from satellites and weather stations (MERRA-2): very good on large scales, less exact for one valley or oasis.",
    "25 years is enough to detect strong trends; small ones may stay 'not proven' until more years are measured.",
    "Future views assume today's measured trend continues in a straight line. They are not forecasts and ignore irrigation changes, new crop varieties and soil.",
    "Crop needs come from FAO ECOCROP averages; real varieties differ, and soil, salinity and water supply are not included.",
    "We never claim why something changes; we say a pattern is consistent with a cause.",
]


if __name__ == "__main__":
    out = {"version": "0.3", "checks": {"cross_check": gistemp_check(), "false_alarms": false_alarm_check(),
                                        "many_places": fdr_check(), "farming": farming_checks()},
           "limitations": LIMITATIONS}
    for path in OUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, v in out["checks"].items():
        print(f"\n[{k}] {v.get('plain', '')}")
        for c in v.get("checks", []):
            print("  ", "PASS" if c["passed"] else "FAIL", c["check"], "|", c["detail"])
