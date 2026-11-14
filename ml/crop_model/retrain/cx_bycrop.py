"""Diagnostic only (not a metric): which crops make the rain-only false alarms / recall, per variant.
Uses the suite's own _run_crop, so the predictions are the ones evalx.run scores."""
import sys

import joblib
import numpy as np
import pandas as pd

import evalx as E
from cx_run import VARIANTS, build
from cx_strategies import CX

ALL = {k: v for g in VARIANTS.values() for k, v in g.items()}


def bycrop(st):
    runs = dict(zip(E.CROPS, joblib.Parallel(n_jobs=E.H.N_JOBS)(joblib.delayed(E._run_crop)(st, c) for c in E.CROPS)))
    S0 = np.column_stack([runs[c]['oof0'] for c in E.CROPS]) >= 0.5
    SU = np.column_stack([runs[c]['oofU'] for c in E.CROPS]) >= 0.5
    Y = E.LAB.to_numpy()
    d = pd.DataFrame({'unf<100': SU[E.SET_DESERT].mean(0), 'unf100-250': SU[E.SET_UNF_SEMI].mean(0), 'semi-irr': S0[E.SEMI_IRR].mean(0),
                      'dryRF n_pres': (Y[E.DRY_RF] == 1).sum(0),
                      'dryRF recall': [(S0[E.DRY_RF][:, j][Y[E.DRY_RF][:, j] == 1]).mean() if (Y[E.DRY_RF][:, j] == 1).any() else np.nan
                                       for j in range(len(E.CROPS))]}, index=E.CROPS)
    return d.round(3)


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    for n in sys.argv[1:]:
        d = bycrop(build(ALL[n]))
        print(f"\n== {n}\n", d[(d.iloc[:, :3].max(1) >= 0.02) | (d['dryRF n_pres'] >= 20)].to_string())
