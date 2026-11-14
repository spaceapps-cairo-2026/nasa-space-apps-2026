"""crop_engine_v3.py - CropShift Earth crop-suitability runtime (v3).

The v2 runtime written by the Kaggle notebook "CropShift Earth v2", plus one documented rule for rain-only mode
(the rain gate, read from the model file's meta "rainfed_rain_gate"; a file without it scores exactly as v2).
Written by ml/crop_model/retrain/train_v3.py. Retrain + regenerate, do not hand-edit.
Dependencies: numpy (+ Python standard library for live NASA POWER requests). No scikit-learn / XGBoost needed at runtime.

    import crop_engine_v3 as ce
    eng = ce.CropSuitabilityEngine.load("crop_suitability_v3.npz")
    report = ce.point_report(eng, lat=30.04, lon=31.24)      # live NASA POWER (6 parameters), any point on Earth
    report = ce.point_report(eng, 30.04, 31.24, irrigation_level=0.5)   # irrigation slider (irrigated mode)
    eng.rank(features_dict, mode="irrigated")                 # features: see ce.FEATURES
    reports = ce.batch_reports(eng, [(key, lat, lon, parameter), ...])  # a whole region, one model call per mode

The model was trained on where 40 crops are actually grown (IFPRI MapSPAM 2020, about 22,000 farmland cells worldwide),
described by 10 climate features computed from the six NASA POWER measurements (T2M, T2M_MAX, PRECTOTCORR, RH2M, GWETTOP, GWETROOT).

Rain gate (rain-only mode, only when no irrigation at all is assumed): the learned score is multiplied by
g(rain) = 0 below r0 mm/year, rising in a straight line to 1 at r1 mm/year. Wheat and barley (winter cereals,
grown on rain alone down to about 200 mm on the Mediterranean and Middle East margins) use 100 to 200 mm; every
other crop uses 100 to 250 mm. The irrigated score is never changed.
"""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request

import numpy as np

P_STRONG, P_MODERATE = 0.01, 0.05
SUIT_THRESHOLD = 0.5
CLASS_EDGES = (0.33, 0.67)
POWER_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
POWER_PARAMS = ["T2M", "T2M_MAX", "PRECTOTCORR", "RH2M", "GWETTOP", "GWETROOT"]
PROJECTION_LABEL = "Projection if the observed trend continues (Theil-Sen extrapolation). Not a forecast."

FEATURES = ['t_mean', 't_coldest', 't_warmest', 'tmax_hottest', 'rain_annual', 'rain_wettest3_share',
            'rh_mean', 'soil_top_wetness', 'soil_root_wetness', 'soil_root_wetness_min']
FEATURE_INFO = {
    't_mean': ('T2M', 'annual mean temperature', 'deg C'),
    't_coldest': ('T2M', 'mean temperature of the coldest month', 'deg C'),
    't_warmest': ('T2M', 'mean temperature of the warmest month', 'deg C'),
    'tmax_hottest': ('T2M_MAX', 'highest monthly maximum temperature of the year (heat stress)', 'deg C'),
    'rain_annual': ('PRECTOTCORR', 'annual rainfall', 'mm/year'),
    'rain_wettest3_share': ('PRECTOTCORR', 'share of the annual rain falling in the wettest 3 consecutive months', '0-1'),
    'rh_mean': ('RH2M', 'annual mean relative humidity', '%'),
    'soil_top_wetness': ('GWETTOP', 'annual mean surface soil wetness', '0-1'),
    'soil_root_wetness': ('GWETROOT', 'annual mean root-zone soil wetness', '0-1'),
    'soil_root_wetness_min': ('GWETROOT', 'root-zone soil wetness of the driest month', '0-1'),
}
FEATURE_BOUNDS = {'rain_annual': (0.0, None), 'rain_wettest3_share': (0.25, 1.0), 'rh_mean': (0.0, 100.0),
                  'soil_top_wetness': (0.0, 1.0), 'soil_root_wetness': (0.0, 1.0), 'soil_root_wetness_min': (0.0, 1.0)}
_DAYS = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


def annual_features(T, TX, P, RH, GT, GR):
    """Each argument: array (..., 12) of monthly NASA POWER values for one year
    (T2M, T2M_MAX in deg C; PRECTOTCORR in mm/day; RH2M in %; GWETTOP, GWETROOT 0-1). Returns (..., 10) in FEATURES order."""
    T, TX, P, RH, GT, GR = (np.asarray(a, dtype=np.float64) for a in (T, TX, P, RH, GT, GR))
    rain_m = P * _DAYS
    rain_y = rain_m.sum(-1)
    ext = np.concatenate([rain_m, rain_m[..., :2]], axis=-1)
    q3 = ext[..., 0:12] + ext[..., 1:13] + ext[..., 2:14]
    share = np.where(rain_y > 1.0, q3.max(-1) / np.maximum(rain_y, 1e-9), 1.0)
    return np.stack([T.mean(-1), T.min(-1), T.max(-1), TX.max(-1), rain_y, share,
                     RH.mean(-1), GT.mean(-1), GR.mean(-1), GR.min(-1)], axis=-1)


def clip_features(F):
    F = np.array(F, dtype=np.float64, copy=True)
    for k, (lo, hi) in FEATURE_BOUNDS.items():
        j = FEATURES.index(k)
        F[..., j] = np.clip(F[..., j], lo if lo is not None else -np.inf, hi if hi is not None else np.inf)
    return F


def suitability_class(s):
    if s is None or not np.isfinite(s):
        return None
    return "high" if s >= CLASS_EDGES[1] else ("medium" if s >= CLASS_EDGES[0] else "low")


def _r(x, nd=2):
    x = float(x)
    return None if not math.isfinite(x) else round(x, nd)


# ---------------------------------------------------------------- packed tree ensembles (numpy evaluator)
class _Pack:
    """All crops' trees in flat arrays; trees are grouped by crop (tree_crop is sorted)."""

    def __init__(self, z, prefix):
        g = lambda k: z[f"{prefix}{k}"]
        self.feature, self.threshold = g("feature").astype(np.intp), g("threshold")
        self.left, self.right, self.value = g("left"), g("right"), g("value")
        self.default_left, self.is_leaf = g("default_left"), g("is_leaf")
        self.roots, self.tree_crop = g("roots"), g("tree_crop")
        self.kind = str(g("kind"))
        self.base = g("base")                     # per-crop base score
        # XGBoost and scikit-learn forests compare float32 inputs: round the same way to reproduce them exactly
        self.f32 = bool(z[f"{prefix}input_f32"]) if f"{prefix}input_f32" in z.files else False
        self.n_crops = int(self.base.size)
        self.start = np.searchsorted(self.tree_crop, np.arange(self.n_crops))
        self.count = np.bincount(self.tree_crop, minlength=self.n_crops)

    def predict(self, X, chunk=128):
        X = np.atleast_2d(np.asarray(X, np.float64))
        if self.f32:
            X = X.astype(np.float32).astype(np.float64)
        out = np.empty((len(X), self.n_crops))
        for s in range(0, len(X), chunk):
            x = X[s:s + chunk]
            node = np.broadcast_to(self.roots[:, None], (self.roots.size, len(x))).copy()
            cols = np.arange(len(x))[None, :]
            while True:
                act = ~self.is_leaf[node]
                if not act.any():
                    break
                xv = x[cols, self.feature[node]]
                go_left = np.where(np.isnan(xv), self.default_left[node], xv <= self.threshold[node])
                node = np.where(act, np.where(go_left, self.left[node], self.right[node]), node)
            sums = np.add.reduceat(self.value[node], self.start, axis=0).T          # (n, n_crops)
            if self.kind == "gbdt":
                out[s:s + chunk] = 1.0 / (1.0 + np.exp(-(sums + self.base[None, :])))
            else:
                out[s:s + chunk] = sums / self.count[None, :]
        return out


class CropSuitabilityEngine:
    """s[crop](10 NASA climate features, irrigation). Modes: 'irrigated' (water supplied) and 'rainfed'."""

    def __init__(self, z):
        self.meta = json.loads(str(z["meta_json"]))
        self.version = self.meta["version"]
        self.crops = list(self.meta["crops"])
        self.n_crops = len(self.crops)
        self.modes = {}
        packs = {}
        for mode, spec in self.meta["modes"].items():
            if spec["prefix"] not in packs:
                packs[spec["prefix"]] = _Pack(z, spec["prefix"])
            self.modes[mode] = {"pack": packs[spec["prefix"]], "features": [FEATURES.index(f) for f in spec["features"]],
                                "irrigation_input": spec.get("irrigation_input"), "irrigation_value": spec.get("irrigation_value")}
        self.train_lo = np.array(self.meta["training_range"]["min"], float)
        self.train_hi = np.array(self.meta["training_range"]["max"], float)
        self._native = {}
        gate = self.meta.get("rainfed_rain_gate")
        self.rain_gate = None
        if gate:
            lo = np.array([gate["by_crop"].get(c, gate["default"])[0] for c in self.crops], float)
            hi = np.array([gate["by_crop"].get(c, gate["default"])[1] for c in self.crops], float)
            self.rain_gate = (lo, hi)

    @classmethod
    def load(cls, path):
        return cls(np.load(path, allow_pickle=False))

    def attach_native(self, prefix, fn):
        """Optional speed-up for bulk runs: fn(X) -> (n, n_crops) from the original library models.
        The numpy evaluator stays the reference; the notebook checks both agree before attaching."""
        self._native[prefix] = fn

    def suitability(self, F, mode="irrigated", irrigation_level=1.0):
        """F: (n, 10) features in FEATURES order -> (n, n_crops) suitability in [0, 1]."""
        if mode not in self.modes:
            raise ValueError(f"mode must be one of {list(self.modes)}")
        F = clip_features(np.atleast_2d(np.asarray(F, np.float64)))
        spec = self.modes[mode]
        X = F[:, spec["features"]]
        if spec["irrigation_input"] is not None:
            fixed = spec.get("irrigation_value")
            lvl = float(fixed) if fixed is not None else float(np.clip(irrigation_level, 0.0, 1.0))
            X = np.column_stack([X, np.full(len(X), lvl)])
        bad = ~np.isfinite(X).all(axis=1)
        Xc = np.where(np.isfinite(X), X, 0.0)
        fn = self._native.get(self.meta["modes"][mode]["prefix"])
        out = np.asarray(fn(Xc), float) if fn is not None else spec["pack"].predict(Xc)
        if self.rain_gate is not None and spec["irrigation_input"] is not None and lvl == 0.0:
            out = out * self.gate_factor(F[:, FEATURES.index("rain_annual")])
        out[bad] = np.nan
        return np.clip(out, 0.0, 1.0)

    def gate_factor(self, rain):
        """(n,) rain in mm/year -> (n, n_crops) rain gate in [0, 1] (all ones when the model has no gate)."""
        rain = np.asarray(rain, float)[:, None]
        if self.rain_gate is None:
            return np.ones((rain.shape[0], self.n_crops))
        lo, hi = self.rain_gate
        return np.clip((rain - lo[None, :]) / (hi - lo)[None, :], 0.0, 1.0)

    def in_training_range(self, F):
        """True where every feature lies inside the range seen in the training farmland (min to max)."""
        F = np.atleast_2d(np.asarray(F, float))
        return ((F >= self.train_lo) & (F <= self.train_hi)).all(axis=1)

    def rank(self, features, mode="irrigated", irrigation_level=1.0):
        F = np.array([[features[k] for k in FEATURES]], float) if isinstance(features, dict) else np.atleast_2d(features)
        s = self.suitability(F, mode, irrigation_level)[0]
        return [{"crop": self.crops[k], "suitability": _r(s[k], 3), "class": suitability_class(s[k])} for k in np.argsort(-s)]


# ---------------------------------------------------------------- trend statistics (same as v1)
def theil_sen_batch(Y, t, chunk=20000):
    Y = np.atleast_2d(np.asarray(Y, float))
    t = np.asarray(t, float)
    i, j = np.triu_indices(t.size, 1)
    dt_ = t[j] - t[i]
    b = np.empty(len(Y))
    for s in range(0, len(Y), chunk):
        b[s:s + chunk] = np.median((Y[s:s + chunk, j] - Y[s:s + chunk, i]) / dt_, axis=1)
    a = np.median(Y - b[:, None] * t[None, :], axis=1)
    return a, b


def mann_kendall_batch(Y, decimals=None, chunk=20000):
    Y = np.atleast_2d(np.asarray(Y, float))
    if decimals is not None:
        Y = np.round(Y, decimals)
    n = Y.shape[1]
    i, j = np.triu_indices(n, 1)
    S = np.empty(len(Y))
    for s in range(0, len(Y), chunk):
        S[s:s + chunk] = np.sign(Y[s:s + chunk, j] - Y[s:s + chunk, i]).sum(axis=1)
    var = np.full(len(Y), n * (n - 1) * (2 * n + 5) / 18.0)
    for k in range(len(Y)):
        _, cnt = np.unique(Y[k], return_counts=True)
        cnt = cnt[cnt > 1]
        if cnt.size:
            var[k] -= float((cnt * (cnt - 1) * (2 * cnt + 5)).sum()) / 18.0
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(var > 0, (S - np.sign(S)) / np.sqrt(np.where(var > 0, var, 1.0)), 0.0)
    p = np.array([math.erfc(abs(v) / math.sqrt(2.0)) for v in z])
    return S, z, p


def confidence_labels(p, slope=None, min_effect=0.0):
    p = np.atleast_1d(np.asarray(p, float))
    lab = np.where(p < P_STRONG, "strong evidence", np.where(p < P_MODERATE, "moderate evidence", "not proven"))
    lab = np.where(np.isfinite(p), lab, "not proven")
    if slope is not None and min_effect > 0:
        lab = np.where(np.abs(np.atleast_1d(slope)) < min_effect, "not proven", lab)
    return lab


def direction_labels(slope, conf, up="gaining", down="losing", none="no proven change"):
    slope = np.atleast_1d(np.asarray(slope, float))
    return np.where(np.asarray(conf) == "not proven", none, np.where(slope > 0, up, down))


def block_bootstrap_indices(n, n_boot=200, block_len=3, seed=42):
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(n / block_len)
    starts = rng.integers(0, n - block_len + 1, size=(n_boot, n_blocks))
    return (starts[:, :, None] + np.arange(block_len)[None, None, :]).reshape(n_boot, -1)[:, :n]


def project_series(Y, years, base_year, horizons, idx):
    """Theil-Sen trend extrapolation with residual block bootstrap. The same year indices are used for every
    row, so the features keep their joint year-to-year behaviour (a hot year stays a dry year)."""
    Y = np.atleast_2d(np.asarray(Y, float))
    t = np.asarray(years, float) - float(base_year)
    a, b = theil_sen_batch(Y, t)
    fit = a[:, None] + b[:, None] * t[None, :]
    res = Y - fit
    ystar = fit[:, None, :] + res[:, idx]
    a_s, b_s = theil_sen_batch(ystar.reshape(-1, t.size), t)
    H = np.asarray(horizons, float)
    point = a[:, None] + b[:, None] * H[None, :]
    draws = a_s.reshape(len(Y), -1)[..., None] + b_s.reshape(len(Y), -1)[..., None] * H
    return {"point": point, "draws": draws, "slope": b}


# ---------------------------------------------------------------- NASA POWER
def fetch_power_point(lat, lon, start=2001, end=2025, timeout=90):
    q = urllib.parse.urlencode({"parameters": ",".join(POWER_PARAMS), "community": "AG", "longitude": f"{lon:.4f}",
                                "latitude": f"{lat:.4f}", "start": int(start), "end": int(end), "format": "JSON"})
    with urllib.request.urlopen(f"{POWER_URL}?{q}", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["properties"]["parameter"]


def yearly_features(parameter):
    """parameter: {'T2M': {'YYYYMM': v}, ...} for the six POWER_PARAMS -> years (n,), features (n, 10).
    Only complete years (12 valid months of all six measurements) are used."""
    keys = sorted(k for k in parameter["T2M"] if k[4:] != "13")
    years = sorted({int(k[:4]) for k in keys})
    ys, rows = [], []
    for y in years:
        M = np.full((6, 12), np.nan)
        for m in range(1, 13):
            for vi, v in enumerate(POWER_PARAMS):
                val = parameter.get(v, {}).get(f"{y}{m:02d}")
                if val is not None and np.isfinite(val) and val > -900:
                    M[vi, m - 1] = float(val)
        if np.isfinite(M).all():
            ys.append(y)
            rows.append(annual_features(*M))
    return np.array(ys, int), np.array(rows, float).reshape(-1, len(FEATURES))


# ---------------------------------------------------------------- report (API payload, v1-compatible + features block)
def _prepare(parameter, base_year=None, horizons=(5, 10), n_boot=200, block_len=3, seed=42):
    """Yearly features, Mann-Kendall per feature and Theil-Sen projections with block-bootstrap draws."""
    years, Fy = yearly_features(parameter)
    if len(years) < 10:
        raise ValueError("need at least 10 complete years of all six NASA POWER measurements (land points only)")
    base_year = int(years[-1]) if base_year is None else int(base_year)
    horizons = [int(h) for h in horizons]
    H = np.array([0] + horizons, float)
    idx = block_bootstrap_indices(len(years), n_boot, block_len, seed)
    proj = project_series(Fy.T, years, base_year, H, idx)
    pt = clip_features(proj["point"].T)                              # (H, 10)
    dr = clip_features(np.transpose(proj["draws"], (1, 2, 0)))       # (B, H, 10)
    _, _, p_f = mann_kendall_batch(Fy.T)
    return {"years": years, "Fy": Fy, "base_year": base_year, "horizons": horizons, "H": H, "n_boot": int(n_boot),
            "proj": proj, "pt": pt, "dr": dr, "p_f": p_f}


def _rows(prep):
    """All feature rows one report needs: trend values (H), bootstrap draws (B x H), observed years."""
    return np.vstack([prep["pt"], prep["dr"].reshape(-1, len(FEATURES)), prep["Fy"]])


def _split(prep, S):
    nH, nB = len(prep["H"]), prep["n_boot"]
    return S[:nH], S[nH:nH + nB * nH].reshape(nB, nH, -1), S[nH + nB * nH:]


def _in_polygon(lat, lon, poly):
    """Ray-casting point-in-polygon test; poly is a list of (lon, lat) vertices."""
    inside, n = False, len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def data_flags_for(engine, lat, lon):
    """Data-quality flags stored in the model file (e.g. a possible data break in one NASA measurement over a region)
    that apply at this point."""
    return [f for f in engine.meta.get("data_flags", []) if not f.get("polygon") or _in_polygon(lat, lon, f["polygon"])]


def _assemble(engine, lat, lon, prep, scores, irrigation_level=1.0, include_series=True,
              min_effect_suit=0.02, min_effect_options=0.10, top=8):
    years, Fy, pt, dr, proj, p_f = (prep[k] for k in ("years", "Fy", "pt", "dr", "proj", "p_f"))
    base_year, horizons, H, n_boot = prep["base_year"], prep["horizons"], prep["H"], prep["n_boot"]
    conf_f = confidence_labels(p_f)
    feats = {}
    for k, name in enumerate(FEATURES):
        src, desc, unit = FEATURE_INFO[name]
        e = {"nasa_parameter": src, "description": desc, "unit": unit, "now": _r(pt[0, k], 3),
             "trend_per_decade": _r(proj["slope"][k] * 10, 4), "p_value": _r(p_f[k], 4), "confidence": str(conf_f[k])}
        for hi, h in enumerate(horizons, start=1):
            d = dr[:, hi, k]
            e[f"plus{h}"] = {"point": _r(pt[hi, k], 3), "median": _r(np.median(d), 3), "p10": _r(np.percentile(d, 10), 3),
                             "p90": _r(np.percentile(d, 90), 3)}
        if include_series:
            e["series"] = [_r(v, 3) for v in Fy[:, k]]
        feats[name] = e
    flags = data_flags_for(engine, lat, lon)
    for fl in flags:
        for name in fl.get("features", []):
            if name in feats:
                feats[name]["data_quality_note"] = fl["note"]
    # v1-compatible climate block (temperature in deg C, rainfall in mm/month)
    climate = {}
    for name, k, scale, unit in [("temperature_c", 0, 1.0, "deg C"), ("rainfall_mm_month", 4, 1 / 12.0, "mm/month")]:
        f = feats[FEATURES[k]]
        e = {"unit": unit, "now": _r(pt[0, k] * scale), "trend_per_decade": _r(proj["slope"][k] * 10 * scale, 4),
             "p_value": f["p_value"], "confidence": f["confidence"]}
        for hi, h in enumerate(horizons, start=1):
            d = dr[:, hi, k] * scale
            e[f"plus{h}"] = {"point": _r(pt[hi, k] * scale), "median": _r(np.median(d)), "p10": _r(np.percentile(d, 10)),
                             "p90": _r(np.percentile(d, 90))}
        if include_series:
            e["series"] = {"years": [int(y) for y in years], "values": [_r(v * scale, 3) for v in Fy[:, k]]}
        if "data_quality_note" in f:
            e["data_quality_note"] = f["data_quality_note"]
        climate[name] = e
    in_range = engine.in_training_range(pt)
    tyears = years - base_year
    modes = {}
    for mode, (s_pt, s_dr, s_ann) in scores.items():
        y2 = np.round(s_ann.T, 2)
        _, _, p_s = mann_kendall_batch(y2)
        _, b_s = theil_sen_batch(y2, tyears)
        conf_s = confidence_labels(p_s, b_s * 10, min_effect_suit)
        dir_s = direction_labels(b_s * 10, conf_s)
        crops = {}
        for ci, c in enumerate(engine.crops):
            e = {"now": _r(s_pt[0, ci], 3), "class": suitability_class(s_pt[0, ci]),
                 "trend": {"per_decade": _r(b_s[ci] * 10, 4), "p_value": _r(p_s[ci], 4),
                           "confidence": str(conf_s[ci]), "direction": str(dir_s[ci])}}
            now_in = bool(s_pt[0, ci] >= SUIT_THRESHOLD)
            for hi, h in enumerate(horizons, start=1):
                d = s_dr[:, hi, ci]
                p_cross = float(np.mean(d < SUIT_THRESHOLD)) if now_in else float(np.mean(d >= SUIT_THRESHOLD))
                e[f"plus{h}"] = {"point": _r(s_pt[hi, ci], 3), "median": _r(np.median(d), 3),
                                 "p10": _r(np.percentile(d, 10), 3), "p90": _r(np.percentile(d, 90), 3),
                                 "class": suitability_class(s_pt[hi, ci]), "p_cross": _r(p_cross, 3),
                                 "cross": (("loses suitability" if now_in else "becomes suitable") if p_cross >= 0.5 else None)}
            if include_series:
                e["series"] = [_r(v, 3) for v in s_ann[:, ci]]
            crops[c] = e
        ranking = {}
        for hi, h in enumerate(H):
            key = "now" if h == 0 else f"plus{int(h)}"
            ranking[key] = [{"crop": engine.crops[j], "suitability": _r(s_pt[hi, j], 3)} for j in np.argsort(-s_pt[hi])[:top]]
        opt_pt, opt_dr, opt_ann = s_pt.sum(1), s_dr.sum(2), s_ann.sum(1)
        top3 = np.sort(s_pt, axis=1)[:, -3:].mean(1)
        yv = np.round(opt_ann[None, :], 2)
        _, _, p_v = mann_kendall_batch(yv)
        _, b_v = theil_sen_batch(yv, tyears)
        conf_v = confidence_labels(p_v, b_v * 10, min_effect_options)
        via = {"crop_options_now": _r(opt_pt[0], 2), "viability_index_now": _r(opt_pt[0] / engine.n_crops, 3),
               "top3_mean_now": _r(top3[0], 3), "n_suitable_now": int((s_pt[0] >= SUIT_THRESHOLD).sum()),
               "trend": {"per_decade": _r(b_v[0] * 10, 3), "p_value": _r(p_v[0], 4), "confidence": str(conf_v[0]),
                         "direction": str(direction_labels(b_v * 10, conf_v)[0])}}
        for hi, h in enumerate(horizons, start=1):
            delta = opt_dr[:, hi] - opt_dr[:, 0]
            via[f"plus{h}"] = {"crop_options_point": _r(opt_pt[hi]), "crop_options_median": _r(np.median(opt_dr[:, hi])),
                               "p10": _r(np.percentile(opt_dr[:, hi], 10)), "p90": _r(np.percentile(opt_dr[:, hi], 90)),
                               "delta_median": _r(np.median(delta)), "delta_p10": _r(np.percentile(delta, 10)),
                               "delta_p90": _r(np.percentile(delta, 90)), "p_decline": _r(np.mean(delta < 0), 3),
                               "top3_mean_point": _r(top3[hi], 3), "n_suitable_point": int((s_pt[hi] >= SUIT_THRESHOLD).sum())}
        if include_series:
            via["series"] = [_r(v, 3) for v in opt_ann]
        modes[mode] = {"crops": crops, "ranking": ranking, "viability": via}
    rep = {"engine_version": engine.version, "location": {"lat": float(lat), "lon": float(lon)},
           "period": {"start": int(years[0]), "end": int(years[-1]), "base_year": base_year, "horizons": horizons},
           "irrigation_level": float(irrigation_level), "projection_label": PROJECTION_LABEL,
           "climate": climate, "features": feats,
           "in_training_range": {("now" if h == 0 else f"plus{int(h)}"): bool(v) for h, v in zip(H, in_range)},
           "modes": modes, "data_quality_notes": [fl["note"] for fl in flags]}
    rep["summary"] = summary_text(rep)
    return rep


def point_report(engine, lat, lon, parameter=None, start=2001, end=2025, base_year=None, horizons=(5, 10),
                 n_boot=200, block_len=3, seed=42, irrigation_level=1.0, include_series=True,
                 min_effect_suit=0.02, min_effect_options=0.10, top=8):
    """Full report for one point. parameter: NASA POWER monthly dict {'T2M': {'YYYYMM': v}, ...}; fetched live if None."""
    if parameter is None:
        parameter = fetch_power_point(lat, lon, start, end)
    prep = _prepare(parameter, base_year, horizons, n_boot, block_len, seed)
    R = _rows(prep)
    scores = {mode: _split(prep, engine.suitability(R, mode, irrigation_level)) for mode in engine.modes}
    return _assemble(engine, lat, lon, prep, scores, irrigation_level, include_series, min_effect_suit, min_effect_options, top)


def batch_reports(engine, points, base_year=None, horizons=(5, 10), n_boot=200, block_len=3, seed=42,
                  irrigation_level=1.0, include_series=False, min_effect_suit=0.02, min_effect_options=0.10, top=8):
    """points: iterable of (key, lat, lon, parameter). Same statistics as point_report (identical output per point),
    but the model is called once per mode for all points, which is much faster for a whole region."""
    points = list(points)
    preps = [_prepare(p, base_year, horizons, n_boot, block_len, seed) for _, _, _, p in points]
    rows = [_rows(pr) for pr in preps]
    cuts = np.cumsum([0] + [len(r) for r in rows])
    allrows = np.vstack(rows)
    S_all = {mode: engine.suitability(allrows, mode, irrigation_level) for mode in engine.modes}
    out = {}
    for i, ((key, lat, lon, _), pr) in enumerate(zip(points, preps)):
        scores = {mode: _split(pr, S[cuts[i]:cuts[i + 1]]) for mode, S in S_all.items()}
        out[key] = _assemble(engine, lat, lon, pr, scores, irrigation_level, include_series, min_effect_suit, min_effect_options, top)
    return out


def summary_text(rep):
    """Plain-language sentence built only from computed numbers (PROJECT_PLAN F1 wording rules)."""
    t, r = rep["climate"]["temperature_c"], rep["climate"]["rainfall_mm_month"]
    f = rep["features"]
    y0, h, by = rep["period"]["start"], rep["period"]["horizons"][-1], rep["period"]["base_year"]
    verb = "rose" if (t["trend_per_decade"] or 0) > 0 else "fell"
    out = [f"Since {y0}, average temperature here {verb} by {abs(t['trend_per_decade'] or 0):.2f} °C per decade ({t['confidence']}).",
           f"Rainfall changed by {r['trend_per_decade'] or 0:+.2f} mm/month per decade ({r['confidence']}); "
           f"root-zone soil wetness by {f['soil_root_wetness']['trend_per_decade'] or 0:+.3f} per decade "
           f"({f['soil_root_wetness']['confidence']})."]
    flagged = [lab for lab, e in (("temperature", t), ("rainfall", r)) if e.get("data_quality_note")]
    if flagged:
        out.append(f"NASA POWER {' and '.join(flagged)} here may contain a data break, so treat that trend with caution.")
    irr = rep["modes"]["irrigated"]
    n = len(irr["crops"])
    best = [x["crop"] for x in irr["ranking"]["now"][:3] if (x["suitability"] or 0) >= SUIT_THRESHOLD]
    out.append(f"With irrigation, the best-fitting crops today are {', '.join(best)}." if best
               else f"With irrigation, none of the {n} crops fits this climate well today.")
    gains = [c for c, e in irr["crops"].items() if e[f"plus{h}"]["cross"] == "becomes suitable"]
    losses = [c for c, e in irr["crops"].items() if e[f"plus{h}"]["cross"] == "loses suitability"]
    if gains or losses:
        parts = []
        if gains:
            parts.append("likely becomes suitable: " + ", ".join(gains))
        if losses:
            parts.append("likely loses suitability: " + ", ".join(losses))
        out.append(f"If current trends continue, by {by + h} " + "; ".join(parts) + ".")
    else:
        out.append(f"If current trends continue, no crop is expected to cross the suitability threshold by {by + h}.")
    if "rainfed" in rep["modes"]:
        out.append(f"Rain-fed: {rep['modes']['rainfed']['viability']['n_suitable_now']} of {n} crops fit today.")
    if not rep["in_training_range"].get("now", True):
        out.append("Note: this climate lies partly outside the range of the training farmland, so treat the ranking with care.")
    return " ".join(out)
