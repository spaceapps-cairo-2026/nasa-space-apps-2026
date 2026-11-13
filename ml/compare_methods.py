"""Lane A, task A3: evidence for decision D1 (which confidence method).

Run:  python ml/compare_methods.py

Three checks:
1. False alarms: series with NO trend but with autocorrelation. A fair test says "significant"
   for about 5% of them. More than that = the method invents trends.
2. Power: series WITH a real trend. Higher = the method finds real changes more often.
3. Egypt grid (real data): how many cells each method calls significant, before and after FDR,
   and a cross-check of our fast array code against the pymannkendall library.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
import trends as T  # noqa: E402

N_YEARS = 25
N_SIM = 20000


def ar1(rho: float, n_series: int, rng: np.random.Generator) -> np.ndarray:
    """Trendless series where each year keeps a share rho of the previous year (unit variance)."""
    x = np.empty((n_series, N_YEARS + 50))
    x[:, 0] = rng.standard_normal(n_series)
    noise = rng.standard_normal(x.shape) * np.sqrt(1 - rho ** 2)
    for t in range(1, x.shape[1]):
        x[:, t] = rho * x[:, t - 1] + noise[:, t]
    return x[:, 50:]


def simulate() -> None:
    rng = np.random.default_rng(2026)
    print(f"\n1. FALSE ALARMS: share of {N_SIM} trendless series called significant at p < 0.05 (fair = 5%)")
    print("   rho = how strongly one year resembles the previous one")
    rhos = [0.0, 0.2, 0.4, 0.6]
    print("   method  " + "".join(f"rho={r:<6}" for r in rhos))
    sims = {r: ar1(r, N_SIM, rng) for r in rhos}
    for m in T.METHODS:
        rates = [np.nanmean(T.trend_grid(sims[r], m)["p"] < 0.05) for r in rhos]
        print(f"   {m:6s}  " + "".join(f"{x:<10.1%}" for x in rates))

    print("\n2. POWER: share of series with a REAL trend that are detected (higher is better)")
    print("   trend = total change over 25 years, in units of the year to year noise")
    cases = [(0.0, 1.5), (0.3, 1.5), (0.3, 2.5), (0.5, 2.5)]
    print("   method  " + "".join(f"rho={r},x{c:<5}" for r, c in cases))
    for m in T.METHODS:
        rates = []
        for r, c in cases:
            x = ar1(r, N_SIM, rng) + np.linspace(0, c, N_YEARS)
            rates.append(np.nanmean(T.trend_grid(x, m)["p"] < 0.05))
        print(f"   {m:6s}  " + "".join(f"{x:<13.1%}" for x in rates))


def egypt() -> None:
    df = pd.read_parquet(ROOT / "data" / "processed" / "power_monthly.parquet")
    print("\n3. EGYPT GRID (357 cells, 2001 to 2025, annual means)")
    print("   variable      lag-1 autocorr   cells significant: p < 0.05 / after FDR q < 0.05")
    print("                 (median)         " + "".join(f"{m:<12}" for m in T.METHODS))
    for var, g in df.groupby("variable"):
        wide = g.pivot(index="cell_id", columns="time", values="value").sort_index(axis=1)
        annual = T.annual_means(wide.to_numpy())
        res = {m: T.trend_grid(annual, m) for m in T.METHODS}
        resid = annual - res["mk"]["slope"][:, None] / 10 * np.arange(annual.shape[1])
        r1 = np.nanmedian(T._acf(resid, 1))
        cols = []
        for m in T.METHODS:
            p = res[m]["p"]
            cols.append(f"{int(np.nansum(p < 0.05))}/{int(np.nansum(T.fdr_bh(p) < 0.05))}")
        print(f"   {var:12s}  {r1:+.2f}            " + "".join(f"{c:<12}" for c in cols))

    # Cross-check against the reference library on real series.
    import pymannkendall as pmk
    wide = df[df.variable == "T2M"].pivot(index="cell_id", columns="time", values="value").sort_index(axis=1)
    annual = T.annual_means(wide.to_numpy())
    ours_mk, ours_hr = T.trend_grid(annual, "mk"), T.trend_grid(annual, "hr")
    worst = 0.0
    for k in range(0, len(annual), 7):
        ref_mk, ref_hr = pmk.original_test(annual[k]), pmk.hamed_rao_modification_test(annual[k])
        worst = max(worst, abs(ref_mk.p - ours_mk["p"][k]), abs(ref_hr.p - ours_hr["p"][k]),
                    abs(ref_mk.slope * 10 - ours_mk["slope"][k]))
    print(f"\n   Cross-check vs pymannkendall (51 cells, plain and Hamed-Rao p, Sen slope): "
          f"largest difference {worst:.2e}")


def speed() -> None:
    rng = np.random.default_rng(1)
    print("\n4. SPEED of the chosen default method on random data")
    for cells in (357, 5000, 207936):
        x = rng.standard_normal((cells, N_YEARS))
        t0 = time.perf_counter()
        T.trend_grid(x)
        print(f"   {cells:>7} cells: {time.perf_counter() - t0:.2f} s")


if __name__ == "__main__":
    simulate()
    egypt()
    speed()
