"""Pack fitted scikit-learn models (one per crop) into the app's .npz format and check that the numpy
runtime (crop_engine_v2.py) reproduces them. Packers are the notebook's pack_forest / pack_hgb, unchanged."""
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import crop_engine_v2 as ce  # noqa: E402
import harness as H  # noqa: E402

OLD_NPZ = HERE.parent / "crop_suitability_v2.npz"


def _finish(feat, thr, left, right, val, dleft, roots, kind, base, f32=False):
    feat = np.array(feat, np.int16)
    left, right = np.array(left, np.int32), np.array(right, np.int32)
    leaf = feat < 0
    left[leaf] = np.where(leaf)[0]
    right[leaf] = np.where(leaf)[0]          # leaves point to themselves
    return {'feature': np.where(leaf, 0, feat).astype(np.int16), 'threshold': np.array(thr, np.float64), 'left': left, 'right': right,
            'value': np.array(val, np.float64), 'default_left': np.array(dleft, bool), 'is_leaf': leaf,
            'roots': np.array(roots, np.int32), 'kind': kind, 'base': float(base), 'f32': f32}


def pack_hgb(model):
    feat, thr, left, right, val, dleft, roots = [], [], [], [], [], [], []
    for it in model._predictors:
        nodes, off = it[0].nodes, len(feat)
        roots.append(off)
        for nd in nodes:
            leaf = bool(nd['is_leaf'])
            feat.append(-1 if leaf else int(nd['feature_idx'])); thr.append(float(nd['num_threshold']))
            left.append(-1 if leaf else off + int(nd['left'])); right.append(-1 if leaf else off + int(nd['right']))
            val.append(float(nd['value']) if leaf else 0.0); dleft.append(bool(nd['missing_go_to_left']))
    return _finish(feat, thr, left, right, val, dleft, roots, 'gbdt', float(np.ravel(model._baseline_prediction)[0]))


def pack_forest(model):
    feat, thr, left, right, val, dleft, roots = [], [], [], [], [], [], []
    for t in model.estimators_:
        tr, off = t.tree_, len(feat)
        roots.append(off)
        v = tr.value[:, 0, :]
        p1 = v[:, 1] / np.maximum(v.sum(1), 1e-12)
        for i in range(tr.node_count):
            leaf = tr.children_left[i] == -1
            feat.append(-1 if leaf else int(tr.feature[i])); thr.append(float(tr.threshold[i]))
            left.append(-1 if leaf else off + int(tr.children_left[i])); right.append(-1 if leaf else off + int(tr.children_right[i]))
            val.append(float(p1[i])); dleft.append(True)
    return _finish(feat, thr, left, right, val, dleft, roots, 'forest', 0.0, f32=True)   # scikit-learn trees compare float32 inputs


def pack_one(model):
    if hasattr(model, 'estimators_'):
        return pack_forest(model)
    if hasattr(model, '_predictors'):
        return pack_hgb(model)
    raise TypeError(f"cannot pack {type(model).__name__}")


def write_npz(models, path, version, algorithm, params, extra_meta=None):
    """models: {crop: fitted estimator} in H.CROPS order. Meta is copied from the v2 file and updated."""
    packs = [pack_one(models[c]) for c in H.CROPS]
    assert len({p['kind'] for p in packs}) == 1 and len({p['f32'] for p in packs}) == 1
    cat = {k: [] for k in ('feature', 'threshold', 'left', 'right', 'value', 'default_left', 'is_leaf', 'roots', 'tree_crop')}
    off = 0
    for ci, pk in enumerate(packs):
        for k in ('feature', 'threshold', 'value', 'default_left', 'is_leaf'):
            cat[k].append(pk[k])
        for k in ('left', 'right', 'roots'):
            cat[k].append(pk[k] + off)
        cat['tree_crop'].append(np.full(pk['roots'].size, ci, np.int16))
        off += pk['feature'].size
    pfx = 'c_'
    arrays = {pfx + k: np.concatenate(v) for k, v in cat.items()}
    arrays[pfx + 'kind'] = np.array(packs[0]['kind'])
    arrays[pfx + 'base'] = np.array([pk['base'] for pk in packs], np.float64)
    arrays[pfx + 'input_f32'] = np.array(bool(packs[0]['f32']))
    old = json.loads(str(np.load(OLD_NPZ, allow_pickle=False)["meta_json"]))
    assert old['crops'] == H.CROPS and old['features'] == H.FEATURES
    meta = dict(old)
    meta.update({'version': version, 'algorithm': algorithm, 'params': params,
                 'trained_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')})
    meta.update(extra_meta or {})
    np.savez_compressed(path, meta_json=np.array(json.dumps(meta)), **arrays)
    return {'trees': int(arrays[pfx + 'roots'].size), 'nodes': int(arrays[pfx + 'feature'].size), 'megabytes': Path(path).stat().st_size / 1e6}


def fidelity(models, path, n=3000, seed=42):
    """Largest difference between the numpy runtime and the library models, both water modes."""
    eng = ce.CropSuitabilityEngine.load(path)
    F = H.farm[H.FEATURES].sample(n, random_state=seed).to_numpy()
    eg = H.farm.loc[H.EGYPT, H.FEATURES].to_numpy()
    out = {}
    for label, Fx in (('world sample', F), ('Egypt farmland', eg)):
        Fc = ce.clip_features(Fx)
        for mode, lvl in (('irrigated', 1.0), ('rainfed', 0.0)):
            a = eng.suitability(Fx, mode)
            b = np.column_stack([models[c].predict_proba(np.column_stack([Fc, np.full(len(Fc), lvl)]))[:, 1] for c in H.CROPS])
            out[f'{label}, {mode}'] = {'rows': len(Fx), 'max_abs_diff': float(np.nanmax(np.abs(a - b))),
                                       'same_suitable_call': float(np.mean((a >= 0.5) == (b >= 0.5)))}
    return out


if __name__ == "__main__":
    import evalx as E
    st = E.Strategy()
    models = E.final_models(st)
    path = HERE / "test_baseline_et.npz"
    info = write_npz(models, path, "test-et", "Extra trees", {'n_estimators': 100, 'min_samples_leaf': 20, 'max_features': 0.8, 'max_depth': 8})
    print(info, "nodes by count:", E.count_nodes(models))
    for k, v in fidelity(models, path).items():
        print(k, v)
