"""Local training harness: the notebook's data prep, labels, spatial folds, counter-examples and metrics,
copied faithfully from cropshift_v2_crop_suitability.py (sections 4 to 8), scikit-learn only.
The counter-example rule is pluggable so variants can be compared on the same folds and metrics."""
import os
import time
import warnings
from functools import partial
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[3]
TABLE = ROOT / "ml/crop_model/training/cropshift_v2_training_cells.parquet"
SEED = 42
N_JOBS = int(os.environ.get("N_JOBS", 20))
CFG = dict(farmland_min_ha=1000, present_share=0.02, absent_share=0.002, block_deg=10, n_folds=5, irrigated_eval_share=0.8,
           rainfed_eval_share=0.2, suit_threshold=0.5, counter_irr_share=0.95, dry_rain_mm=100)
CROP_NAMES = {
    'whea': 'wheat', 'rice': 'rice', 'maiz': 'maize', 'barl': 'barley', 'pmil': 'pearl millet', 'mill': 'small millets',
    'sorg': 'sorghum', 'pota': 'potato', 'swpo': 'sweet potato', 'yams': 'yams', 'cass': 'cassava', 'bean': 'beans',
    'chic': 'chickpea', 'cowp': 'cowpea', 'pige': 'pigeon pea', 'lent': 'lentil', 'soyb': 'soybean', 'grou': 'groundnut',
    'cnut': 'coconut', 'oilp': 'oil palm', 'sunf': 'sunflower', 'rape': 'rapeseed', 'sesa': 'sesame', 'sugc': 'sugarcane',
    'sugb': 'sugar beet', 'cott': 'cotton', 'coff': 'arabica coffee', 'rcof': 'robusta coffee', 'coco': 'cocoa',
    'teas': 'tea', 'toba': 'tobacco', 'bana': 'banana', 'plnt': 'plantain', 'citr': 'citrus', 'trof': 'tropical fruit',
    'temf': 'temperate fruit', 'toma': 'tomato', 'onio': 'onion', 'vege': 'vegetables', 'rubb': 'rubber'}
CODES = list(CROP_NAMES)
CROPS = [CROP_NAMES[c] for c in CODES]
FEATURES = ['t_mean', 't_coldest', 't_warmest', 'tmax_hottest', 'rain_annual', 'rain_wettest3_share',
            'rh_mean', 'soil_top_wetness', 'soil_root_wetness', 'soil_root_wetness_min']
COLS = FEATURES + ['irr_share']
RAIN = FEATURES.index('rain_annual')

cells_all = pd.read_parquet(TABLE)
farm = cells_all[cells_all.TA_total >= CFG['farmland_min_ha']].reset_index(drop=True)
farm['irr_share'] = (farm.TI_total / farm.TA_total).clip(0, 1).astype(float)


def share_labels(tab, prefix='TA_', pres=CFG['present_share'], absn=CFG['absent_share']):
    out = {}
    tot = np.maximum(tab['TA_total'].to_numpy(float), 1.0)
    for code, name in CROP_NAMES.items():
        s = tab[prefix + code].to_numpy(float) / tot
        out[name] = np.where(s >= pres, 1.0, np.where(s <= absn, 0.0, np.nan))
    return pd.DataFrame(out, index=tab.index)


def area_labels(tab, pres=CFG['present_share'], absn=CFG['absent_share'], pres_ha=1000.0, abs_ha=200.0):
    """Present also when the crop is grown at scale (>= pres_ha in the cell) though under 2% of a big cell's harvest;
    absent only when <= 0.2% AND < abs_ha. Set CROPSHIFT_LABELS=area (read here, so parallel workers agree)."""
    out = {}
    tot = np.maximum(tab['TA_total'].to_numpy(float), 1.0)
    for code, name in CROP_NAMES.items():
        a = tab['TA_' + code].to_numpy(float)
        s = a / tot
        out[name] = np.where((s >= pres) | (a >= pres_ha), 1.0, np.where((s <= absn) & (a < abs_ha), 0.0, np.nan))
    return pd.DataFrame(out, index=tab.index)


LABELS = os.environ.get("CROPSHIFT_LABELS", "share")
PRES_HA = float(os.environ.get("CROPSHIFT_PRES_HA", 1000))
LAB = area_labels(farm, pres_ha=PRES_HA, abs_ha=min(200.0, PRES_HA / 5)) if LABELS == "area" else share_labels(farm)
X_ALL = farm[COLS].to_numpy(float)
GROUPS = (np.floor((farm.lat + 90) / CFG['block_deg']) * 1000 + np.floor((farm.lon + 180) / CFG['block_deg'])).astype(int).to_numpy()
FOLDS = list(GroupKFold(n_splits=CFG['n_folds']).split(X_ALL, groups=GROUPS))
EGYPT = (farm.country == 'Egypt').to_numpy()
IRR_DOM = (farm.irr_share >= CFG['irrigated_eval_share']).to_numpy()
RF_DOM = (farm.irr_share <= CFG['rainfed_eval_share']).to_numpy()
DRY_IRR = ((farm.irr_share >= CFG['counter_irr_share']) & (farm.rain_annual < CFG['dry_rain_mm'])).to_numpy()
_fold_of = {g: k for k, (_, te) in enumerate(FOLDS) for g in np.unique(GROUPS[te])}


def unfarmed(max_rain, min_rain=0.0):
    """Unfarmed cells (< farmland_min_ha) with min_rain <= rain < max_rain, as rain-fed rows, their fold, Egypt flag."""
    d = cells_all[(cells_all.TA_total < CFG['farmland_min_ha']) & (cells_all.rain_annual < max_rain)
                  & (cells_all.rain_annual >= min_rain)].reset_index(drop=True)
    X = np.column_stack([d[FEATURES].to_numpy(float), np.zeros(len(d))])
    g = (np.floor((d.lat + 90) / CFG['block_deg']) * 1000 + np.floor((d.lon + 180) / CFG['block_deg'])).astype(int).to_numpy()
    fold = np.array([_fold_of.get(v, v % CFG['n_folds']) for v in g])
    return d, X, fold, d.country.eq('Egypt').to_numpy()


# the notebook's evaluation set of unfarmed deserts (also its counter-example set)
DESERT, X_DESERT, DESERT_FOLD, DESERT_EGYPT = unfarmed(CFG['dry_rain_mm'])


def bal_w(y):
    p = float(np.mean(y))
    return np.where(y == 1, 0.5 / p, 0.5 / (1 - p))


class ConstantModel:
    def __init__(self, p):
        self.p = float(p)

    def predict_proba(self, X):
        return np.column_stack([np.full(len(X), 1 - self.p), np.full(len(X), self.p)])


class Counter:
    """Rain-fed counter-examples, all 'not grown' at irrigation share 0.
    irr_share: copy training cells with at least this irrigated share (the notebook: 0.95).
    irr_rain_max: if set, also copy cells with irrigated share >= irr_share2 and rain below this.
    desert_rain: unfarmed cells with less rain than this (the notebook: 100)."""

    def __init__(self, irr_share=0.95, desert_rain=100, irr_share2=None, irr_rain_max=None):
        self.irr_share, self.irr_share2, self.irr_rain_max = irr_share, irr_share2, irr_rain_max
        _, self.XD, self.Dfold, self.Deg = unfarmed(desert_rain)

    def rows(self, X, desert_mask):
        m = X[:, -1] >= self.irr_share
        if self.irr_share2 is not None:
            m |= (X[:, -1] >= self.irr_share2) & (X[:, RAIN] < self.irr_rain_max)
        Xc = X[m].copy()
        Xc[:, -1] = 0.0
        return np.vstack([Xc, self.XD[desert_mask]])

    def fold_mask(self, k):
        return self.Dfold != k

    def no_egypt_mask(self):
        return ~self.Deg

    def all_mask(self):
        return np.ones(len(self.XD), bool)


def fit_model(make, X, y, X_counter=None):
    if X_counter is not None and len(X_counter):
        X, y = np.vstack([X, X_counter]), np.concatenate([y, np.zeros(len(X_counter))])
    if len(np.unique(y)) < 2:
        return ConstantModel(float(np.mean(y)) if len(y) else 0.0)
    return make().fit(X, y, sample_weight=bal_w(y))


def run_crop(make, crop, cs, egypt=False, post=None):
    """Spatial CV for one crop (as the notebook's run_crop). cs: Counter or None.
    post(p, X): optional post-processing applied identically to every prediction."""
    y = LAB[crop].to_numpy()
    X = X_ALL
    n = len(y)
    o, o1, o0 = (np.full(n, np.nan) for _ in range(3))
    oD = np.full(len(DESERT_FOLD), np.nan)
    lab = ~np.isnan(y)

    def pred(m, Z):
        p = m.predict_proba(Z)[:, 1]
        return p if post is None else post(p, Z)

    for k, (tr, te) in enumerate(FOLDS):
        m = fit_model(make, X[tr[lab[tr]]], y[tr[lab[tr]]], cs.rows(X[tr], cs.fold_mask(k)) if cs else None)
        o[te] = pred(m, X[te])
        if (DESERT_FOLD == k).any():
            oD[DESERT_FOLD == k] = pred(m, X_DESERT[DESERT_FOLD == k])
        X1, X0 = X[te].copy(), X[te].copy()
        X1[:, -1], X0[:, -1] = 1.0, 0.0
        o1[te], o0[te] = pred(m, X1), pred(m, X0)
    res = {'oof': o, 'oof1': o1, 'oof0': o0, 'oofD': oD}
    if egypt:
        tr = np.where(lab & ~EGYPT)[0]
        m = fit_model(make, X[tr], y[tr], cs.rows(X[~EGYPT], cs.no_egypt_mask()) if cs else None)
        Xe1, Xe0 = X[EGYPT].copy(), X[EGYPT].copy()
        Xe1[:, -1], Xe0[:, -1] = 1.0, 0.0
        res['egypt'], res['egypt0'] = pred(m, Xe1), pred(m, Xe0)
        res['egypt_model'] = m
    return res


def crop_metrics(y, r):
    ok = ~np.isnan(y)
    yy, pp = y[ok], r['oof'][ok]
    pos, neg = yy == 1, yy == 0
    out = {'AUC': roc_auc_score(yy, pp),
           'TSS': float((pp[pos] >= 0.5).mean() - (pp[neg] >= 0.5).mean()),
           'Brier': float(np.average((pp - yy) ** 2, weights=bal_w(yy)))}
    for key, mask, p in [('AUC irr', IRR_DOM, r['oof1']), ('AUC rf', RF_DOM, r['oof0'])]:
        k = ok & mask
        out[key] = roc_auc_score(y[k], p[k]) if (y[k] == 1).sum() >= 20 and (y[k] == 0).sum() >= 20 else np.nan
    out['FA dry-irr'] = float((r['oof0'][DRY_IRR] >= 0.5).mean())
    out['FA desert'] = float((r['oofD'] >= 0.5).mean())
    return out


def evaluate(make, cs, egypt=True, post=None, crops=None):
    crops = crops or CROPS
    runs = joblib.Parallel(n_jobs=N_JOBS)(joblib.delayed(run_crop)(make, c, cs, egypt, post) for c in crops)
    per = pd.DataFrame([crop_metrics(LAB[c].to_numpy(), r) for c, r in zip(crops, runs)], index=crops)
    return per, dict(zip(crops, runs))


MAKERS = {
    'ET': partial(ExtraTreesClassifier, n_jobs=1, random_state=SEED, n_estimators=100, min_samples_leaf=20, max_features=0.8, max_depth=8),
}

if __name__ == "__main__":
    print(f"{len(farm):,} farmland | Egypt {EGYPT.sum()} | irr>=.8 {IRR_DOM.sum():,} | rf<=.2 {RF_DOM.sum():,} | "
          f">=.95 {(farm.irr_share >= .95).sum()} dry {DRY_IRR.sum()} | deserts {len(DESERT):,}")
    t0 = time.time()
    per, runs = evaluate(MAKERS['ET'], Counter(), egypt=False)
    print(per.mean().round(4).to_dict(), "worst AUC", round(per.AUC.min(), 4), per.AUC.idxmin(), f"{time.time() - t0:.0f}s")
    print("notebook ET tuned: AUC .8955 irr .8148 rf .8795 TSS .6382 Brier .1273 FA .0080 / .0229 worst .8069")
