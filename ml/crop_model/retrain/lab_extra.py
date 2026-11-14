"""Extra read-outs for the best lab variants (evalx untouched: its _run_crop is only called).
1. rain-fed AUC restricted to held-out rain-fed farmland (irr_share <= 0.2) with rain >= R, and the size of the part below R
2. which crops are still scored >= .5 on rain in Egypt's farmland cells with >= 100 mm (model trained without Egypt)
3. tree nodes of the deployable model
python lab_extra.py name1 name2 ...
"""
import json
import sys
from collections import Counter

import joblib
import numpy as np
from sklearn.metrics import roc_auc_score

import evalx as E
import harness as H
import lab_strategies as L

RAIN = H.farm.rain_annual.to_numpy()


def rf_auc(runs, lo, hi=1e9):
    out = []
    for c in E.CROPS:
        y = E.LAB[c].to_numpy()
        k = ~np.isnan(y) & H.RF_DOM & (RAIN >= lo) & (RAIN < hi)
        if (y[k] == 1).sum() >= 20 and (y[k] == 0).sum() >= 20:
            out.append(roc_auc_score(y[k], runs[c]['oof0'][k]))
    return float(np.mean(out)), len(out)


if __name__ == "__main__":
    res = {}
    for name in sys.argv[1:]:
        st = L.get(name)
        runs = dict(zip(E.CROPS, joblib.Parallel(n_jobs=H.N_JOBS)(joblib.delayed(E._run_crop)(st, c) for c in E.CROPS)))
        r = {}
        for R in (0, 100, 150, 200, 300):
            r[f'AUC rf rain>={R}'], r[f'n crops rain>={R}'] = rf_auc(runs, R)
        r['AUC rf 150<=rain<300'], r['n crops 150-300'] = rf_auc(runs, 150, 300)
        Y = E.LAB.to_numpy()
        S0 = np.column_stack([runs[c]['oof0'] for c in E.CROPS]) >= 0.5
        for lo, hi in ((0, 150), (150, 300), (300, 500), (500, 1e9)):
            m = H.RF_DOM & (RAIN >= lo) & (RAIN < hi)
            r[f'rf recall {lo}-{hi:.0f}'] = float(S0[m][Y[m] == 1].mean())
            r[f'rf false alarm {lo}-{hi:.0f}'] = float(S0[m][Y[m] == 0].mean())
        for c in ('wheat', 'barley'):
            i = E.CROPS.index(c)
            p = Y[E.DRY_RF][:, i] == 1
            r[f'dry RF recall {c}'] = float(S0[E.DRY_RF][:, i][p].mean())
            r[f'n {c}'] = int(p.sum())
        E0 = np.column_stack([runs[c]['eg0'] for c in E.CROPS]) >= 0.5
        wet = E.EG_RAIN >= 100
        r['EG rf>=100 crops'] = dict(Counter({c: int(E0[wet][:, i].sum()) for i, c in enumerate(E.CROPS) if E0[wet][:, i].sum()}).most_common())
        r['EG rf>=100 cells with any crop'] = int((E0[wet].sum(1) > 0).sum())
        r['EG rf<50 cells with any crop'] = int((E0[E.EG_RAIN < 50].sum(1) > 0).sum())
        r['EG n cells >=100'] = int(wet.sum())
        if name != 'lab-none':
            r['nodes'] = E.count_nodes(E.final_models(st))
        res[name] = r
        print(name, json.dumps(r, indent=1))
        sys.stdout.flush()
    (E.HERE / "lab_extra.json").write_text(json.dumps(res, indent=1))
    print("held-out rain-fed farmland: total", int(H.RF_DOM.sum()), "| rain<100", int((H.RF_DOM & (RAIN < 100)).sum()),
          "| rain<150", int((H.RF_DOM & (RAIN < 150)).sum()), "| rain<200", int((H.RF_DOM & (RAIN < 200)).sum()))
