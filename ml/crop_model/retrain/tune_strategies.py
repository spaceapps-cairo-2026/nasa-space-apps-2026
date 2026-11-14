"""Fine-tuning sweep of the v3.1 recipe (Sat 14 Nov, second pass): XGBoost settings only, same labels, counter-examples
and rain gate, same fixed held-out suite (evalx.py). Run with the v3.1 labels:
    CROPSHIFT_LABELS=area CROPSHIFT_PRES_HA=500 python tune_strategies.py [names]"""
import sys
import evalx as E
import combo_strategies as C
from xgb_strategies import XCombo

VARIANTS = {
    'tune-base': XCombo(cx=C.CX63, gate=C.GATE),
    'tune-n400': XCombo(cx=C.CX63, gate=C.GATE, n_estimators=400),
    'tune-n600': XCombo(cx=C.CX63, gate=C.GATE, n_estimators=600),
    'tune-n400-d4': XCombo(cx=C.CX63, gate=C.GATE, n_estimators=400, max_depth=4),
    'tune-n400-d8': XCombo(cx=C.CX63, gate=C.GATE, n_estimators=400, max_depth=8),
    'tune-col08': XCombo(cx=C.CX63, gate=C.GATE, colsample_bytree=0.8),
    'tune-mcw5': XCombo(cx=C.CX63, gate=C.GATE, min_child_weight=5),
    'tune-n400-col08-mcw5': XCombo(cx=C.CX63, gate=C.GATE, n_estimators=400, colsample_bytree=0.8, min_child_weight=5),
}
if __name__ == "__main__":
    for n in sys.argv[1:] or VARIANTS:
        E.run(VARIANTS[n], n)
