"""XGBoost (Manus's algorithm and tuned settings) under the same recipes (prefix "xgb")."""
import sys
from xgboost import XGBClassifier
import evalx as E
import combo_strategies as C
H = E.H
XGB0 = dict(n_estimators=200, learning_rate=0.03, max_depth=6, subsample=0.8, colsample_bytree=1.0,
            reg_lambda=20, min_child_weight=1)


class XCombo(C.Combo):
    def __init__(self, cx=None, gate=None, **over):
        super().__init__(cx=cx, gate=gate)
        self.xp = {**XGB0, **over}

    def make(self):
        return XGBClassifier(random_state=H.SEED, n_jobs=1, tree_method='hist', eval_metric='logloss', **self.xp)


VARIANTS = {
    'xgb-v2recipe': XCombo(),
    'xgb-gate': XCombo(gate=C.GATE),
    'xgb-cx63': XCombo(cx=C.CX63),
    'xgb-cx63-gate': XCombo(cx=C.CX63, gate=C.GATE),
}
if __name__ == "__main__":
    for n in sys.argv[1:] or VARIANTS:
        E.run(VARIANTS[n], n)
