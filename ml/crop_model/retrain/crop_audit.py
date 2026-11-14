"""Every crop vs Egypt's reality, for the deployed fit of a recipe.
Reality: FAOSTAT Egypt harvested area (mean 2015-2024, from the notebook) and MapSPAM 2020 per cell.
Usage: CROPSHIFT_LABELS=share|area [CROPSHIFT_PRES_HA=1000] python crop_audit.py"""
import os
import numpy as np
import pandas as pd
import harness as H
import evalx as E
import combo_strategies as C
import xgb_strategies as XS

st = XS.XCombo(cx=C.CX63, gate=C.GATE)
models = E.final_models(st)
eg = H.farm[H.EGYPT]
X1 = H.X_ALL[H.EGYPT].copy(); X1[:, -1] = 1.0
CODE = {v: k for k, v in H.CROP_NAMES.items()}
rows = []
for c in H.CROPS:
    p = 100 * models[c].predict_proba(X1)[:, 1]
    a = eg['TA_' + CODE[c]].to_numpy()
    grown = a >= 500
    rows.append(dict(crop=c, fao_kha=E.FAO_HA.get(c, 0) / 1000, spam_kha=a.sum() / 1000,
                     score_where_grown=np.average(p, weights=a) if a.sum() > 0 else np.nan,
                     cells_ge50=int((p >= 50).sum()), median_all=np.median(p)))
df = pd.DataFrame(rows).sort_values('spam_kha', ascending=False)
pd.set_option('display.width', 200)
print(df.round(1).to_string(index=False))
big = df[df.spam_kha >= 10]
miss = big[big.score_where_grown < 50]
notgrown = df[(df.spam_kha < 1) & (df.fao_kha < 1.5)]
fa = notgrown[notgrown.cells_ge50 > 0]
print(f"\nMISSES (Egypt grows >= 10,000 ha, score < 50 where grown): {len(miss)}: {', '.join(miss.crop)}")
print(f"FALSE ALARMS (Egypt grows < 1,000 ha; cells >= 50): {', '.join(f'{r.crop} ({r.cells_ge50})' for r in fa.itertuples()) or 'none'}")
