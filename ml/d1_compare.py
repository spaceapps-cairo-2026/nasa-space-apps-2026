"""Decision D1: compare candidate trend tests on realistic fake series and on the real Egypt grid.

Check A (false alarms): trendless series with Egypt-like noise and year-to-year resemblance.
Check B (power): same noise plus a known small trend.
Check C (real data): significant cells per variable, before and after FDR.

Run:  python ml/d1_compare.py      Output: printed tables + ml/outputs/d1_compare.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data" / "processed" / "power_monthly.parquet"
OUT = ROOT / "ml" / "outputs" / "d1_compare.json"
START, END = 2001, 2025
N_SIM = 2000
RNG = np.random.default_rng(14112026)


def ols_t(x: np.ndarray) -> float:
    return float(stats.linregress(np.arange(len(x)), x).pvalue)


METHODS = {
    "plain_mk": lambda x: mk.original_test(x).p,
    "hamed_rao_mk": lambda x: mk.hamed_rao_modification_test(x).p,
    "prewhitened_mk": lambda x: mk.pre_whitening_modification_test(x).p,
    "tfpw_mk": lambda x: mk.trend_free_pre_whitening_modification_test(x).p,
    "linear_t_test": ols_t,
}
LABELS = {
    "plain_mk": "Plain Mann-Kendall",
    "hamed_rao_mk": "Mann-Kendall, Hamed-Rao correction",
    "prewhitened_mk": "Mann-Kendall with pre-whitening",
    "tfpw_mk": "Mann-Kendall, trend-free pre-whitening",
    "linear_t_test": "Linear regression t-test",
}


def annual_table(code: str) -> pd.DataFrame:
    """Rows = cells, columns = years, values = annual mean (needs 9+ valid months)."""
    df = pd.read_parquet(GRID)
    df = df[df["variable"] == code].copy()
    df["year"] = df["time"].str[:4].astype(int)
    g = df.groupby(["cell_id", "year"])["value"]
    ann = g.mean().where(g.count() >= 9)
    return ann.unstack("year").loc[:, START:END]


def noise_profile(tab: pd.DataFrame) -> tuple[float, float]:
    """Median residual sd and lag-1 autocorrelation after removing each cell's straight-line trend."""
    sds, rhos = [], []
    t = np.arange(tab.shape[1])
    for _, row in tab.dropna().iterrows():
        x = row.to_numpy()
        res = x - np.polyval(np.polyfit(t, x, 1), t)
        sds.append(res.std(ddof=2))
        if res.std() > 0:
            rhos.append(np.corrcoef(res[:-1], res[1:])[0, 1])
    return float(np.median(sds)), float(np.nanmedian(rhos))


def ar1(n: int, sd: float, rho: float) -> np.ndarray:
    e = RNG.normal(0, sd * np.sqrt(1 - rho**2), n)
    x = np.empty(n)
    x[0] = RNG.normal(0, sd)
    for i in range(1, n):
        x[i] = rho * x[i - 1] + e[i]
    return x


def simulate(sd: float, rho: float, slope_per_year: float) -> dict[str, float]:
    n = END - START + 1
    hits = {m: 0 for m in METHODS}
    for _ in range(N_SIM):
        x = ar1(n, sd, rho) + slope_per_year * np.arange(n)
        for m, f in METHODS.items():
            hits[m] += f(x) < 0.05
    return {m: hits[m] / N_SIM for m in METHODS}


def real_counts(tab: pd.DataFrame) -> dict[str, dict[str, int]]:
    rows = tab.dropna()
    out = {}
    for m, f in METHODS.items():
        p = np.array([f(r.to_numpy()) for _, r in rows.iterrows()], dtype=float)
        ok = np.isfinite(p)  # near-constant desert series can make a test return NaN
        q = multipletests(p[ok], method="fdr_bh")[1] if ok.any() else np.array([])
        out[m] = {"p_below_0.05": int((p[ok] < 0.05).sum()), "q_below_0.05": int((q < 0.05).sum()),
                  "cells": int(len(p)), "no_answer": int((~ok).sum())}
    return out


def main() -> None:
    results: dict = {"n_sim": N_SIM, "period": [START, END], "variables": {}}
    for code in ["T2M", "T2M_MAX", "GWETROOT", "RH2M", "PRECTOTCORR"]:
        tab = annual_table(code)
        sd, rho = noise_profile(tab)
        res = {"noise_sd": sd, "lag1_autocorrelation": rho, "real": real_counts(tab)}
        if code == "T2M":
            res["check_A_false_alarm"] = simulate(sd, rho, 0.0)
            # A modest real trend: 0.2 C per decade, close to Egypt's median warming.
            res["check_B_power_0.2_per_decade"] = simulate(sd, rho, 0.02)
            res["check_A_false_alarm_strong_autocorr"] = simulate(sd, 0.5, 0.0)
        results["variables"][code] = res
        print(f"\n== {code}: noise sd {sd:.3f}, year-to-year resemblance (lag-1) {rho:.2f}")
        for m in METHODS:
            r = res["real"][m]
            extra = ""
            if code == "T2M":
                extra = (f" | false alarms {res['check_A_false_alarm'][m]:.1%}"
                         f" (rho 0.5: {res['check_A_false_alarm_strong_autocorr'][m]:.1%})"
                         f" | finds 0.2C/decade {res['check_B_power_0.2_per_decade'][m]:.1%}")
            print(f"  {LABELS[m]:38s} sig cells p<.05: {r['p_below_0.05']:3d}  after FDR: {r['q_below_0.05']:3d} / {r['cells']}"
                  f" (no answer {r['no_answer']}){extra}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1))
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
