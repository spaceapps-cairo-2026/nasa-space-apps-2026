"""Experiment: labels 'share' (v2/v3: present = >= 2% of the cell's harvest) vs 'area' (also present when >= 1,000 ha).
Run: CROPSHIFT_LABELS=share|area python label_area_test.py   (same v3 recipe; Egypt FAOSTAT is label-independent)."""
import numpy as np
import harness as H
import evalx as E
import combo_strategies as C
import xgb_strategies as XS

CHECK = ['sweet potato', 'beans', 'soybean', 'sesame', 'banana', 'barley', 'groundnut', 'sunflower', 'wheat', 'maize', 'rice', 'tomato']
CODE = {v: k for k, v in H.CROP_NAMES.items()}
st = XS.XCombo(cx=C.CX63, gate=C.GATE)
res = E.run(st, f"label-{H.LABELS}-xgb-cx63-gate", quiet=True)
print(H.LABELS, {k: round(res[k], 4) for k in ('AUC', 'TSS', 'Brier', 'ECE', 'EG FAO AUC', 'EG FAO TSS', 'EG cell AUC', 'crops/cell unf100-250', 'crops/cell semi-irr', 'EG irr fits', 'dry RF recall cereals')})
models = E.final_models(st)
eg = H.farm[H.EGYPT]
X1 = H.X_ALL[H.EGYPT].copy(); X1[:, -1] = 1.0
X0 = X1.copy(); X0[:, -1] = 0.0
line = []
for c in CHECK:
    p = models[c].predict_proba(X1)[:, 1]
    line.append(f"{c} {100 * np.average(p, weights=eg['TA_' + CODE[c]].to_numpy()):.0f}")
print("  deployed fit, area-weighted irrigated score where Egypt grows it:", ", ".join(line))
P = np.column_stack([models[c].predict_proba(X1)[:, 1] for c in H.CROPS])
print(f"  Egypt farmland: crops >= 50 irrigated per cell {np.mean((P >= .5).sum(1)):.1f}")
