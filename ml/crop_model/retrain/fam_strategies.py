"""Estimator-family strategies (prefix "fam"). One class, Fam, covers every variant:
the estimator family and its parameters, and optionally a stronger counter-example setting."""
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier

import evalx as E
import harness as H

N_FEAT = 11  # 10 climate features + irr_share (last)


class Fam(E.Strategy):
    """v2 training recipe with a chosen scikit-learn estimator.

    kind: 'ET', 'RF' or 'HGB'; params: estimator keyword arguments.
    mono_irr: HGB only, monotonic_cst = +1 on irr_share ("supplying water never makes a place less suitable").
    unf_rain: unfarmed cells with less rain than this become rain-fed 'not grown' counter-examples (v2: 100 mm).
    cw: weight multiplier of all counter-example rows relative to ordinary negatives (v2: 1). The class balance
        (positives and negatives carry equal total weight) is kept: negatives are renormalised after the multiplier.
    """

    def __init__(self, kind='ET', params=None, mono_irr=False, unf_rain=100.0, cw=1.0):
        self.kind, self.params, self.mono_irr = kind, dict(params or {}), mono_irr
        self.unf_rain, self.cw = float(unf_rain), float(cw)
        self.name = f"fam-{kind}"

    def make(self):
        p = dict(self.params)
        if self.kind == 'ET':
            return ExtraTreesClassifier(n_jobs=1, random_state=H.SEED, **p)
        if self.kind == 'RF':
            return RandomForestClassifier(n_jobs=1, random_state=H.SEED, **p)
        if self.mono_irr:
            p['monotonic_cst'] = [0] * (N_FEAT - 1) + [1]
        return HistGradientBoostingClassifier(random_state=H.SEED, early_stopping=False, **p)

    def counter(self, Xtr, unf_ok):
        Xc = Xtr[Xtr[:, -1] >= 0.95].copy()
        Xc[:, -1] = 0.0
        return np.vstack([Xc, E.X_UNF[unf_ok & (E.UNF_RAIN < self.unf_rain)]])

    def train_set(self, Xtr, ytr, unf_ok, crop):
        k = ~np.isnan(ytr)
        Xc = self.counter(Xtr, unf_ok)
        Xf, yf = np.vstack([Xtr[k], Xc]), np.concatenate([ytr[k], np.zeros(len(Xc))])
        w = H.bal_w(yf)
        if self.cw != 1.0 and len(Xc):
            neg = yf == 0
            tot = w[neg].sum()
            w[-len(Xc):] *= self.cw
            w[neg] *= tot / w[neg].sum()
        return Xf, yf, w


ET0 = dict(n_estimators=100, min_samples_leaf=20, max_features=0.8, max_depth=8)
RF0 = dict(n_estimators=60, min_samples_leaf=50, max_features='sqrt', max_depth=14)


def hgb(it=300, lr=0.05, leaves=15, msl=50, l2=1.0, mf=1.0, depth=None):
    return dict(max_iter=it, learning_rate=lr, max_leaf_nodes=leaves, min_samples_leaf=msl, l2_regularization=l2,
                max_features=mf, max_depth=depth)


CONFIGS = {
    # --- families under the v2 recipe
    'ET-tuned': Fam('ET', ET0),
    'ET-d10': Fam('ET', {**ET0, 'max_depth': 10}),
    'ET-d12-l10': Fam('ET', {**ET0, 'max_depth': 12, 'min_samples_leaf': 10}),
    'ET-d12-l10-n200': Fam('ET', {**ET0, 'max_depth': 12, 'min_samples_leaf': 10, 'n_estimators': 200}),
    'ET-d14-l10-mf1': Fam('ET', {**ET0, 'max_depth': 14, 'min_samples_leaf': 10, 'max_features': 1.0}),
    'ET-d10-l40': Fam('ET', {**ET0, 'max_depth': 10, 'min_samples_leaf': 40}),
    'ET-d10-l10': Fam('ET', {**ET0, 'max_depth': 10, 'min_samples_leaf': 10}),
    'ET-d11': Fam('ET', {**ET0, 'max_depth': 11}),
    'ET-d9': Fam('ET', {**ET0, 'max_depth': 9}),
    'ET-d10-mf1': Fam('ET', {**ET0, 'max_depth': 10, 'max_features': 1.0}),
    'ET-d10-mf06': Fam('ET', {**ET0, 'max_depth': 10, 'max_features': 0.6}),
    'ET-d10-n200': Fam('ET', {**ET0, 'max_depth': 10, 'n_estimators': 200}),
    'HGB-i': Fam('HGB', hgb(100, 0.05, 15, 100, 5.0, 0.6)),
    # --- stronger counter-examples (unfarmed cells up to 200 mm, counter rows x5), same estimators
    'ET-d10-cx200w5': Fam('ET', {**ET0, 'max_depth': 10}, unf_rain=200, cw=5),
    'ET-tuned-cx200w5': Fam('ET', ET0, unf_rain=200, cw=5),
    'HGB-b-cx200w5': Fam('HGB', hgb(150, 0.05, 15, 100, 5.0), unf_rain=200, cw=5),
    'HGB-b-mono-cx200w5': Fam('HGB', hgb(150, 0.05, 15, 100, 5.0), mono_irr=True, unf_rain=200, cw=5),
    'ET-d12': Fam('ET', {**ET0, 'max_depth': 12}),
    'ET-d11-cx200w5': Fam('ET', {**ET0, 'max_depth': 11}, unf_rain=200, cw=5),
    'ET-d11-cx200w1': Fam('ET', {**ET0, 'max_depth': 11}, unf_rain=200, cw=1),
    'HGB-i-cx200w5': Fam('HGB', hgb(100, 0.05, 15, 100, 5.0, 0.6), unf_rain=200, cw=5),
    'HGB-i-cx200w1': Fam('HGB', hgb(100, 0.05, 15, 100, 5.0, 0.6), unf_rain=200, cw=1),
    'ET-d11-cx100w5': Fam('ET', {**ET0, 'max_depth': 11}, unf_rain=100, cw=5),
    'ET-d11-cx150w1': Fam('ET', {**ET0, 'max_depth': 11}, unf_rain=150, cw=1),
    'ET-d11-cx150w3': Fam('ET', {**ET0, 'max_depth': 11}, unf_rain=150, cw=3),
    'ET-d11-cx150w5': Fam('ET', {**ET0, 'max_depth': 11}, unf_rain=150, cw=5),
    'HGB-i-cx150w3': Fam('HGB', hgb(100, 0.05, 15, 100, 5.0, 0.6), unf_rain=150, cw=3),
    'HGB-i-cx100w5': Fam('HGB', hgb(100, 0.05, 15, 100, 5.0, 0.6), unf_rain=100, cw=5),
    'RF-tuned-cx200w5': Fam('RF', RF0, unf_rain=200, cw=5),
    'RF-tuned': Fam('RF', RF0),
    'RF-l20-n100': Fam('RF', {**RF0, 'n_estimators': 100, 'min_samples_leaf': 20}),
    'RF-l100-d10': Fam('RF', {**RF0, 'min_samples_leaf': 100, 'max_depth': 10}),
    'RF-l50-mf05': Fam('RF', {**RF0, 'max_features': 0.5}),
    'HGB-default': Fam('HGB', hgb(100, 0.1, 31, 20, 0.0)),
    'HGB-a': Fam('HGB', hgb(300, 0.05, 15, 50, 1.0)),
    'HGB-b': Fam('HGB', hgb(150, 0.05, 15, 100, 5.0)),
    'HGB-c': Fam('HGB', hgb(200, 0.03, 7, 100, 5.0)),
    'HGB-d': Fam('HGB', hgb(300, 0.03, 15, 200, 10.0, 0.6)),
    'HGB-e': Fam('HGB', hgb(500, 0.03, 7, 200, 20.0, 0.6)),
    'HGB-f': Fam('HGB', hgb(150, 0.03, 7, 200, 20.0, 0.5)),
    'HGB-g': Fam('HGB', hgb(300, 0.1, 63, 20, 0.0)),
    'HGB-h': Fam('HGB', hgb(150, 0.05, 31, 200, 10.0, 0.6)),
    # --- monotone irrigation
    'HGB-b-mono': Fam('HGB', hgb(150, 0.05, 15, 100, 5.0), mono_irr=True),
    'HGB-c-mono': Fam('HGB', hgb(200, 0.03, 7, 100, 5.0), mono_irr=True),
    'HGB-d-mono': Fam('HGB', hgb(300, 0.03, 15, 200, 10.0, 0.6), mono_irr=True),
    'HGB-f-mono': Fam('HGB', hgb(150, 0.03, 7, 200, 20.0, 0.5), mono_irr=True),
}
