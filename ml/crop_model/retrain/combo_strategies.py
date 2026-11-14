"""Combinations of the four approaches' winners (prefix "combo"). Same fixed suite (evalx)."""
import sys
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
import evalx as E
import cx_strategies as CX
import gate_strategies as G
H = E.H
ET0 = dict(n_estimators=100, min_samples_leaf=20, max_features=0.8, max_depth=8)


class Combo(CX.CXCrop):
    """CXCrop counter-examples (or the v2 recipe if cx=None) + deeper Extra Trees + optional crop-aware rain gate."""

    def __init__(self, depth=11, leaf=20, cx=None, gate=None, n_est=100):
        self.use_cx = cx is not None
        super().__init__(**(cx or {}))
        self.depth, self.leaf, self.gate_args, self.n_est = depth, leaf, gate, n_est
        self._crop = None

    def make(self):
        return ExtraTreesClassifier(n_jobs=1, random_state=H.SEED, **{**ET0, 'max_depth': self.depth,
                                                                     'min_samples_leaf': self.leaf, 'n_estimators': self.n_est})

    def train_set(self, Xtr, ytr, unf_ok, crop):
        self._crop = crop
        if self.use_cx:
            return super().train_set(Xtr, ytr, unf_ok, crop)
        return E.Strategy.train_set(self, Xtr, ytr, unf_ok, crop)

    def post(self, p, Z):
        if self.gate_args is None:
            return p
        c0, c1, r0, r1 = self.gate_args
        rain = Z[:, H.RAIN]
        g = G.linear_gate(rain, c0, c1) if self._crop in G.WINTER_CEREALS else G.linear_gate(rain, r0, r1)
        return G.blend(p, Z, g, 'exact0')


CX63 = dict(unf_rain=250, cw=3, cw_rain=250, exempt_prev=0.25)
CX58 = dict(unf_rain=250, cw=3, cw_rain=250, exempt_prev=0.33)
GATE = (100, 200, 100, 250)
GATE_SOFT = (100, 200, 100, 200)
VARIANTS = {
    'combo-d11-cx63': Combo(11, cx=CX63),
    'combo-d11-cx63-gate': Combo(11, cx=CX63, gate=GATE),
    'combo-d11-gate': Combo(11, gate=GATE),
    'combo-d11-lingate': Combo(11, gate=GATE_SOFT),
    'combo-d12-cx63': Combo(12, cx=CX63),
    'combo-d11-cx58': Combo(11, cx=CX58),
    'combo-d11-cx63-lingate': Combo(11, cx=CX63, gate=GATE_SOFT),
}

if __name__ == "__main__":
    for n in sys.argv[1:] or VARIANTS:
        E.run(VARIANTS[n], n)
