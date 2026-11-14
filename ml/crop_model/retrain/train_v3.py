"""Train, pack and check crop-suitability-v3.1 (about 20 s on 20 CPUs). Needs xgboost + scikit-learn.

    python ml/crop_model/retrain/train_v3.py

What changed from v2 (Manus's notebook), chosen on the fixed held-out suite in evalx.py (see README.md here):
1. Same algorithm and settings: XGBoost, 200 trees, learning rate 0.03, depth 6 (the notebook's tuned values).
2. Stronger rain-only counter-examples (cx_strategies.CXCrop, variant cx-63): unfarmed land up to 250 mm of rain
   (v2: 100 mm) is taught as "not grown on rain alone", dry counter rows count 3 times, except for a crop in the
   50 mm rain bands where the training data shows it is a common rain-fed crop (at least 25% of rain-fed farmland).
3. A rain gate in rain-only mode, stored in the model file and applied by crop_engine_v3.py: 0 below 100 mm,
   rising to 1 at 200 mm (wheat, barley) or 250 mm (all other crops). Irrigated scores are never changed.
4. (v3.1) Labels: a crop is also 'present' where the cell grows >= 500 ha of it (v2: only >= 2% of the cell's
   harvest). Egypt's Nile cells are so large that crops it grows on tens of thousands of hectares (sweet potato,
   beans, sesame, banana, groundnut, barley) were 'absent' almost everywhere, so the model scored them near 0.

Writes ml/crop_model/crop_suitability_v3.npz and ml/crop_model/metrics_v3.json.
"""
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
os.environ['CROPSHIFT_LABELS'], os.environ['CROPSHIFT_PRES_HA'] = 'area', '500'   # read by harness.py (and its workers)
MODEL_DIR = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(MODEL_DIR))

import combo_strategies as C  # noqa: E402
import crop_engine_v3 as ce  # noqa: E402
import evalx as E  # noqa: E402
import pack as PK  # noqa: E402
import xgb_strategies as XS  # noqa: E402

H = E.H
VERSION = "crop-suitability-v3.1"
OUT_NPZ = MODEL_DIR / "crop_suitability_v3.npz"
OUT_METRICS = MODEL_DIR / "metrics_v3.json"
CHOSEN = "label-area500-xgb-cx63-gate"   # results/<CHOSEN>.json holds its held-out numbers
COMPARE = ["xgb-cx63-gate", "label-area1000-xgb-cx63-gate", "label-area2000-xgb-cx63-gate", "xgb-v2recipe", "xgb-gate", "xgb-cx63",
           "combo-d12-gate", "baseline-ET-v2recipe"]
GATE = {"rule": "score x clip((rain_annual - r0) / (r1 - r0), 0, 1) in rain-only mode (irrigation share 0)",
        "default": [100.0, 250.0], "by_crop": {"wheat": [100.0, 200.0], "barley": [100.0, 200.0]},
        "why": "Rain-fed cropping needs about 200 to 250 mm of rain a year; winter wheat and barley reach about 200 mm. "
               "MapSPAM labels some desert farming on groundwater and floods as rain-fed, which taught the model "
               "rain-fed crops in deserts."}


def pack_xgboost(model):
    """The notebook's packer, unchanged. XGBoost tests float32(x) < split; stored as x <= previous float32."""
    booster = model.get_booster()
    feat, thr, left, right, val, dleft, roots = [], [], [], [], [], [], []
    names = booster.feature_names
    fidx = (lambda s: names.index(s)) if names else (lambda s: int(str(s).lstrip('f')))

    def walk(node):
        k = len(feat)
        feat.append(-1); thr.append(0.0); left.append(-1); right.append(-1); val.append(0.0); dleft.append(True)
        if 'leaf' in node:
            val[k] = float(node['leaf'])
            return k
        ch = {c['nodeid']: c for c in node['children']}
        feat[k] = fidx(node['split'])
        thr[k] = float(np.nextafter(np.float32(node['split_condition']), np.float32(-np.inf)))
        dleft[k] = node['missing'] == node['yes']
        left[k] = walk(ch[node['yes']]); right[k] = walk(ch[node['no']])
        return k

    for s in booster.get_dump(dump_format='json'):
        roots.append(walk(json.loads(s)))
    bs = float(json.loads(booster.save_config())['learner']['learner_model_param']['base_score'].strip('[]'))
    return PK._finish(feat, thr, left, right, val, dleft, roots, 'gbdt', math.log(bs / (1 - bs)), f32=True)


def gate_np(rain, crops):
    lo = np.array([GATE["by_crop"].get(c, GATE["default"])[0] for c in crops])
    hi = np.array([GATE["by_crop"].get(c, GATE["default"])[1] for c in crops])
    return np.clip((np.asarray(rain)[:, None] - lo) / (hi - lo), 0, 1)


def fidelity(models, path, n=3000, seed=42):
    """Largest difference between the numpy runtime and XGBoost (+ the gate in rain-only mode)."""
    eng = ce.CropSuitabilityEngine.load(path)
    out = {}
    for label, Fx in (('world sample', H.farm[H.FEATURES].sample(n, random_state=seed).to_numpy()),
                      ('Egypt farmland', H.farm.loc[H.EGYPT, H.FEATURES].to_numpy())):
        Fc = ce.clip_features(Fx)
        for mode, lvl in (('irrigated', 1.0), ('rainfed', 0.0)):
            a = eng.suitability(Fx, mode)
            b = np.column_stack([models[c].predict_proba(np.column_stack([Fc, np.full(len(Fc), lvl)]))[:, 1] for c in H.CROPS])
            if lvl == 0.0:
                b = b * gate_np(Fc[:, H.RAIN], H.CROPS)
            out[f'{label}, {mode}'] = {'rows': len(Fx), 'max_abs_diff': float(np.nanmax(np.abs(a - b))),
                                       'same_suitable_call': float(np.mean((a >= 0.5) == (b >= 0.5)))}
    return out


def main():
    assert H.LABELS == 'area' and H.PRES_HA == 500, 'harness did not pick up the v3.1 labels'
    t0 = time.time()
    st = XS.XCombo(cx=C.CX63)                       # the gate lives in the model file, not in training
    models = E.final_models(st)
    print(f"40 crop models trained on all farmland ({time.time() - t0:.0f} s)")
    packs = {c: pack_xgboost(models[c]) for c in H.CROPS}
    PK.pack_one = lambda m: packs[next(c for c in H.CROPS if models[c] is m)]
    held = json.loads((HERE / "results" / f"{CHOSEN}.json").read_text())["metrics"]
    info = PK.write_npz(models, OUT_NPZ, VERSION, "XGBoost", XS.XGB0, {
        "rainfed_rain_gate": GATE,
        "recipe": {"counter_examples": "CXCrop(unf_rain=250, cw=3, cw_rain=250, exempt_prev=0.25)", "base": "v2 notebook",
                   "labels": "present: >= 2% of the cell's harvest or >= 500 ha; absent: <= 0.2% and < 100 ha"},
        "held_out": {k: round(held[k], 4) for k in ("AUC", "AUC irr", "AUC rf", "TSS", "Brier", "ECE")}})
    fid = fidelity(models, OUT_NPZ)
    worst = max(v['max_abs_diff'] for v in fid.values())
    print(info, f"largest runtime difference {worst:.2e}")
    assert worst < 1e-6, fid
    comp = {n: json.loads((HERE / "results" / f"{n}.json").read_text())["metrics"] for n in [CHOSEN] + COMPARE}
    OUT_METRICS.write_text(json.dumps({
        "version": VERSION, "algorithm": "XGBoost", "params": XS.XGB0, "rainfed_rain_gate": GATE,
        "counter_examples": "cx_strategies.CXCrop(unf_rain=250, cw=3, cw_rain=250, exempt_prev=0.25)",
        "labels": "present: >= 2% of the cell's harvest or >= 500 ha; absent: <= 0.2% and < 100 ha (v2/v3: shares only)",
        "chosen_variant": CHOSEN, "packed_model": {"file": OUT_NPZ.name, **info}, "numpy_runtime_fidelity": fid,
        "held_out_suite": "retrain/evalx.py: 5 folds of whole 10 x 10 degree blocks; Egypt scored by a model trained without Egypt",
        "comparison_held_out": comp}, indent=1))
    print("wrote", OUT_NPZ.name, OUT_METRICS.name, f"({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
