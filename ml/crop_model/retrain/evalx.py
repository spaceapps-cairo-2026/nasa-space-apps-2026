"""FIXED evaluation suite for retraining experiments. Do not change the metrics, the folds or the test sets.

A Strategy only decides (1) the estimator and (2) how the TRAINING set of a fold is built. Everything
that is tested stays the notebook's: 5 folds of whole 10 x 10 degree blocks, the original features, labels
and irrigation shares of the held-out cells, and held-out unfarmed cells assigned to the same blocks.

    import evalx as E
    class Mine(E.Strategy): ...
    res = E.run(Mine(), "my-variant")      # prints one table row, saves results/my-variant.json

Metrics (all on cells the fold's model never saw):
  notebook's 7:  AUC, AUC irr (irrigated farmland scored at share 1), AUC rf (rain-fed farmland at share 0), TSS, Brier,
                 FA dry-irr (rain-fed score >= .5 on farmland >= 95% irrigated with < 100 mm rain), FA desert (unfarmed, < 100 mm)
  worst AUC      lowest crop AUC
  ECE            calibration error, the notebook's definition
  NEW dry-band checks, rain-fed mode (share 0):
    FA semi-irr      share of (cell, crop) scored >= .5 on farmland >= 95% irrigated with 100 <= rain < 250 mm
    FA unf100-250    the same on unfarmed cells (< 1,000 ha) with 100 <= rain < 250 mm
    crops/cell ...   mean number of the 40 crops scored >= .5 per cell in each of those sets (what a user sees on the map)
    dry RF recall    on rain-fed farmland (<= 20% irrigated) with 150 <= rain < 300 mm: share of PRESENT crops scored >= .5
                     at share 0 (true rain-fed farming at the dry margin: must not collapse)
    dry RF recall cereals   the same for wheat and barley only
  Egypt, model trained WITHOUT any Egyptian cell:
    EG cell AUC, EG FAO AUC, EG FAO TSS   as the notebook (irrigated mode)
    EG rf crops<100 / >=100   mean number of crops scored >= .5 in rain-fed mode per Egyptian farmland cell with rain < 100 / >= 100 mm
    EG rf crops unfarmed      the same on Egypt's unfarmed cells of the table
    EG irr fits               mean number of crops scored >= .5 in irrigated mode per Egyptian farmland cell
"""
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)
RAIN = H.RAIN
X, LAB, FOLDS = H.X_ALL, H.LAB, H.FOLDS
CROPS = H.CROPS

# every unfarmed cell of the table (TA < 1,000 ha), in rain-fed form, with its fold and Egypt flag
UNF, X_UNF, UNF_FOLD, UNF_EGYPT = H.unfarmed(1e9)
UNF_RAIN = X_UNF[:, RAIN]
SET_DESERT = UNF_RAIN < 100
SET_UNF_SEMI = (UNF_RAIN >= 100) & (UNF_RAIN < 250)
SEMI_IRR = ((H.farm.irr_share >= 0.95) & (H.farm.rain_annual >= 100) & (H.farm.rain_annual < 250)).to_numpy()
DRY_RF = ((H.farm.irr_share <= 0.2) & (H.farm.rain_annual >= 150) & (H.farm.rain_annual < 300)).to_numpy()
EG = H.EGYPT
EG_RAIN = X[EG][:, RAIN]

FAO_HA = {'wheat': 1376460, 'maize': 1024209, 'rice': 537008, 'vegetables': 328223, 'sugar beet': 237049, 'potato': 213914,
          'citrus': 207547, 'tomato': 170616, 'sorghum': 158088, 'sugarcane': 144638, 'tropical fruit': 140844, 'cotton': 99543,
          'onion': 88878, 'groundnut': 65684, 'temperate fruit': 61982, 'beans': 41185, 'sesame': 35422, 'banana': 30148,
          'barley': 25070, 'soybean': 22788, 'sunflower': 14580, 'sweet potato': 12960, 'cowpea': 1982, 'chickpea': 1303, 'lentil': 497}
_ha = np.array([float(FAO_HA.get(c, 0.0)) for c in CROPS])
FAO_GROWN = np.where(_ha >= 10000, 1.0, np.where(_ha <= 1500, 0.0, np.nan))
W_EG = H.farm.loc[EG, 'TA_total'].to_numpy()


class Strategy:
    """Default = the notebook's v2 training recipe with tuned Extra Trees."""
    name = "v2-recipe"

    def make(self):
        return H.MAKERS['ET']()

    def counter(self, Xtr, unf_ok):
        """Extra 'not grown' rows for every crop. Xtr: all farmland rows of the training folds (11 columns, the last
        is the irrigation share). unf_ok: mask over X_UNF of unfarmed cells that may be used (training folds only)."""
        Xc = Xtr[Xtr[:, -1] >= 0.95].copy()
        Xc[:, -1] = 0.0
        return np.vstack([Xc, X_UNF[unf_ok & SET_DESERT]])

    def train_set(self, Xtr, ytr, unf_ok, crop):
        """-> X, y, sample_weight for one crop. ytr has NaN where the label is uncertain."""
        k = ~np.isnan(ytr)
        Xc = self.counter(Xtr, unf_ok)
        Xf, yf = np.vstack([Xtr[k], Xc]), np.concatenate([ytr[k], np.zeros(len(Xc))])
        return Xf, yf, H.bal_w(yf)

    def post(self, p, Z):
        """Optional rule applied to every prediction (Z = the rows that were scored). Default: none."""
        return p


def _fit(st, Xtr, ytr, unf_ok, crop):
    Xf, yf, w = st.train_set(Xtr, ytr, unf_ok, crop)
    if len(np.unique(yf)) < 2:
        return H.ConstantModel(float(np.mean(yf)) if len(yf) else 0.0)
    return st.make().fit(Xf, yf, sample_weight=w)


def _run_crop(st, crop):
    y = LAB[crop].to_numpy()
    n = len(y)
    o, o1, o0 = (np.full(n, np.nan) for _ in range(3))
    oU = np.full(len(X_UNF), np.nan)

    def pred(m, Z):
        return np.clip(st.post(m.predict_proba(Z)[:, 1], Z), 0, 1)

    for k, (tr, te) in enumerate(FOLDS):
        m = _fit(st, X[tr], y[tr], UNF_FOLD != k, crop)
        o[te] = pred(m, X[te])
        X1, X0 = X[te].copy(), X[te].copy()
        X1[:, -1], X0[:, -1] = 1.0, 0.0
        o1[te], o0[te] = pred(m, X1), pred(m, X0)
        u = UNF_FOLD == k
        if u.any():
            oU[u] = pred(m, X_UNF[u])
    m = _fit(st, X[~EG], y[~EG], ~UNF_EGYPT, crop)          # leave Egypt out
    Xe1, Xe0 = X[EG].copy(), X[EG].copy()
    Xe1[:, -1], Xe0[:, -1] = 1.0, 0.0
    return {'oof': o, 'oof1': o1, 'oof0': o0, 'oofU': oU, 'eg1': pred(m, Xe1), 'eg0': pred(m, Xe0),
            'egU': pred(m, X_UNF[UNF_EGYPT]) if UNF_EGYPT.any() else np.array([])}


def _ece(runs, bins=np.linspace(0, 1, 11)):
    P, Y, W = [], [], []
    for c in CROPS:
        y = LAB[c].to_numpy()
        k = ~np.isnan(y)
        P.append(runs[c]['oof'][k]); Y.append(y[k]); W.append(H.bal_w(y[k]) / k.sum())
    P, Y, W = map(np.concatenate, (P, Y, W))
    b = np.clip(np.digitize(P, bins) - 1, 0, len(bins) - 2)
    ece = tot = 0.0
    for i in np.unique(b):
        g = b == i
        ece += W[g].sum() * abs(np.average(P[g], weights=W[g]) - np.average(Y[g], weights=W[g]))
        tot += W[g].sum()
    return ece / tot


def run(st, name=None, n_jobs=None, save=True, quiet=False):
    name = name or st.name
    t0 = time.time()
    runs = dict(zip(CROPS, joblib.Parallel(n_jobs=n_jobs or H.N_JOBS)(joblib.delayed(_run_crop)(st, c) for c in CROPS)))
    per = pd.DataFrame([H.crop_metrics(LAB[c].to_numpy(), {**runs[c], 'oofD': runs[c]['oofU'][SET_DESERT]}) for c in CROPS], index=CROPS)
    out = {k: float(v) for k, v in per.mean().items()}
    out['worst AUC'] = float(per.AUC.min())
    out['ECE'] = float(_ece(runs))
    S0 = np.column_stack([runs[c]['oof0'] for c in CROPS]) >= 0.5        # farmland, rain-fed mode
    SU = np.column_stack([runs[c]['oofU'] for c in CROPS]) >= 0.5        # unfarmed, rain-fed mode
    Y = LAB.to_numpy()
    out['FA semi-irr'] = float(S0[SEMI_IRR].mean())
    out['FA unf100-250'] = float(SU[SET_UNF_SEMI].mean())
    out['crops/cell dry-irr'] = float(S0[H.DRY_IRR].sum(1).mean())
    out['crops/cell desert'] = float(SU[SET_DESERT].sum(1).mean())
    out['crops/cell semi-irr'] = float(S0[SEMI_IRR].sum(1).mean())
    out['crops/cell unf100-250'] = float(SU[SET_UNF_SEMI].sum(1).mean())
    pres = Y[DRY_RF] == 1
    out['dry RF recall'] = float(S0[DRY_RF][pres].mean())
    ci = [CROPS.index('wheat'), CROPS.index('barley')]
    out['dry RF recall cereals'] = float(S0[DRY_RF][:, ci][pres[:, ci]].mean())
    E1 = np.column_stack([runs[c]['eg1'] for c in CROPS])
    E0 = np.column_stack([runs[c]['eg0'] for c in CROPS]) >= 0.5
    yy, pp = Y[EG].T.ravel(), E1.T.ravel()
    k = ~np.isnan(yy)
    out['EG cell AUC'] = float(roc_auc_score(yy[k], pp[k]))
    nat = np.average(E1, axis=0, weights=W_EG)
    g = ~np.isnan(FAO_GROWN)
    out['EG FAO AUC'] = float(roc_auc_score(FAO_GROWN[g], nat[g]))
    out['EG FAO TSS'] = float((nat[FAO_GROWN == 1] >= 0.5).mean() - (nat[FAO_GROWN == 0] >= 0.5).mean())
    out['EG rf crops<100'] = float(E0[EG_RAIN < 100].sum(1).mean())
    out['EG rf crops>=100'] = float(E0[EG_RAIN >= 100].sum(1).mean())
    EU = np.column_stack([runs[c]['egU'] for c in CROPS]) >= 0.5
    out['EG rf crops unfarmed'] = float(EU.sum(1).mean())
    out['EG irr fits'] = float((E1 >= 0.5).sum(1).mean())
    out['seconds'] = round(time.time() - t0, 1)
    if save:
        (RESULTS / f"{name}.json").write_text(json.dumps({'name': name, 'metrics': out, 'per_crop_auc': per.AUC.round(4).to_dict()}, indent=1))
    if not quiet:
        show(name, out)
    return out


def final_models(st, n_jobs=None):
    """The deployable models: one per crop, fitted on ALL farmland with all counter-examples (as the notebook's fit_final)."""
    ok = np.ones(len(X_UNF), bool)
    fits = joblib.Parallel(n_jobs=n_jobs or H.N_JOBS)(joblib.delayed(_fit)(st, X, LAB[c].to_numpy(), ok, c) for c in CROPS)
    return dict(zip(CROPS, fits))


def count_nodes(models):
    """Tree nodes of the fitted models = size of the packed app model. Budget: 2,000,000 for all 40 crops."""
    n = 0
    for m in models.values():
        if hasattr(m, 'estimators_'):
            n += sum(e.tree_.node_count for e in m.estimators_)
        elif hasattr(m, '_predictors'):
            n += sum(len(p[0].nodes) for p in m._predictors)
    return int(n)


COLS1 = ['AUC', 'AUC irr', 'AUC rf', 'TSS', 'Brier', 'FA dry-irr', 'FA desert', 'worst AUC', 'ECE']
COLS2 = ['FA semi-irr', 'FA unf100-250', 'crops/cell desert', 'crops/cell semi-irr', 'crops/cell unf100-250', 'dry RF recall', 'dry RF recall cereals']
COLS3 = ['EG cell AUC', 'EG FAO AUC', 'EG FAO TSS', 'EG rf crops<100', 'EG rf crops>=100', 'EG rf crops unfarmed', 'EG irr fits']


def show(name, out):
    print(f"\n[{name}]  ({out.get('seconds', '?')} s)")
    for cols in (COLS1, COLS2, COLS3):
        print("   " + " | ".join(f"{c} {out[c]:.4f}" if abs(out[c]) < 10 else f"{c} {out[c]:.2f}" for c in cols))


def table(names=None):
    rows = {}
    for p in sorted(RESULTS.glob("*.json")):
        d = json.loads(p.read_text())
        if names is None or d['name'] in names:
            rows[d['name']] = d['metrics']
    return pd.DataFrame(rows).T


if __name__ == "__main__":
    print(f"unfarmed pool {len(X_UNF):,} (desert<100: {SET_DESERT.sum():,}, 100-250: {SET_UNF_SEMI.sum():,}, Egypt: {UNF_EGYPT.sum()}) | "
          f"semi-irr farmland {SEMI_IRR.sum()} | dry rain-fed farmland {DRY_RF.sum()} | Egypt farmland {EG.sum()} (rain>=100: {(EG_RAIN >= 100).sum()})")
    run(Strategy(), "baseline-ET-v2recipe")
