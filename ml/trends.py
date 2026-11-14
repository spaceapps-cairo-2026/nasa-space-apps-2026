"""Lane A: the trend engine (task A4). Plain words for every step: docs/METHODS.md.

Two questions are answered for every place and measurement:

1. HOW MUCH is it changing?  Sen's slope: the median of the slopes between every pair of years,
   reported per decade in the measurement's real unit, with a 95% range.
2. COULD IT JUST BE LUCK?    Mann-Kendall test, corrected for autocorrelation (one year resembling
   the previous one). It gives p: how often a trend at least this strong would show up if nothing
   were really changing. On a map, p of every cell is turned into q (false discovery rate), so
   that testing hundreds of cells does not produce a crowd of lucky "trends".

Everything works on whole arrays [cells, years] at once, never a Python loop over cells, so a
country is computed in milliseconds and the whole world (207,936 cells) in a few seconds.

Main entry points:
    trend_grid(annual)                 arrays in, arrays out (any number of cells)
    trend_one(series)                  one place
    change_point(series, years)        year the level shifted (Pettitt test), or None
    confidence_levels(q)               0 = not proven, 1 = moderate, 2 = strong
"""
from __future__ import annotations

import warnings

import numpy as np
from scipy.stats import norm, rankdata

START_YEAR, END_YEAR = 2001, 2025
MIN_MONTHS_PER_YEAR = 9      # a year with fewer valid months has no annual mean
MIN_YEARS = 20               # full record: a place with fewer valid years gets "no data"
MIN_RANGE_YEARS = 10         # the shortest year range a user may ask a trend for
MIN_VALID_SHARE = 0.8        # share of the chosen years that must have data
ALPHA = 0.05
CURVE_MIN_YEARS = 20         # D1 update (Sat): from this length, noise memory is measured after a curve

# D1: the confidence method. See docs/DECISIONS.md and ml/compare_methods.py for the evidence.
DEFAULT_METHOD = "ess"
METHODS = {
    "mk": "Mann-Kendall, no autocorrelation correction",
    "hr": "Mann-Kendall, Hamed-Rao variance correction (all lags)",
    "hr3": "Mann-Kendall, Hamed-Rao variance correction (lags 1 to 3, never below plain variance)",
    "pw": "Mann-Kendall after pre-whitening (lag 1 autocorrelation removed)",
    "tfpw": "Mann-Kendall after trend-free pre-whitening (Yue-Pilon)",
    "ess": "Mann-Kendall, variance scaled by lag 1 autocorrelation of what is left after a smooth curve (20+ years; a straight line for shorter ranges), effective sample size, bias corrected",
    "ess_line": "Mann-Kendall, variance scaled by lag 1 autocorrelation of what is left after a straight line (D1 until Sat 14 Nov)",
    "ws": "Mann-Kendall after iterative pre-whitening (Wang-Swail, bias corrected)",
}

# D2: confidence levels, applied to q on maps and to p for a single place.
STRONG, MODERATE = 0.01, 0.05
LEVEL_NAMES = ["not proven", "moderate evidence", "strong evidence"]

_CHUNK = 20000               # cells per batch, keeps memory small for the world grid


def annual_means(monthly, min_months: int = MIN_MONTHS_PER_YEAR) -> np.ndarray:
    """Monthly values [..., years * 12] -> yearly means [..., years]. This removes the seasons."""
    m = np.asarray(monthly, dtype=np.float64)
    by_year = m.reshape(*m.shape[:-1], -1, 12)
    valid = np.isfinite(by_year).sum(axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.nansum(by_year, axis=-1) / valid
    out[valid < min_months] = np.nan
    return out


def _plain(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Mann-Kendall score S, its variance without correction, Sen slope per step, valid count."""
    n_t = x.shape[1]
    i, j = np.triu_indices(n_t, 1)
    d = x[:, j] - x[:, i]                                   # NaN when either year is missing
    s = np.nansum(np.sign(d), axis=1)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        slope = np.nanmedian(d / (j - i), axis=1)
    n = np.isfinite(x).sum(axis=1).astype(np.float64)
    # Ties (equal values) reduce the variance. c = how many values equal each value.
    c = (x[:, :, None] == x[:, None, :]).sum(axis=2).astype(np.float64)
    tie_term = np.where(c > 0, (c - 1) * (2 * c + 5), 0.0).sum(axis=1)
    var = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    return s, var, slope, n


def _acf(y: np.ndarray, lag: int) -> np.ndarray:
    """Autocorrelation at one lag for every row; missing values count as 'average'."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        y = y - np.nanmean(y, axis=1, keepdims=True)
    y = np.where(np.isfinite(y), y, 0.0)
    den = (y * y).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (y[:, :-lag] * y[:, lag:]).sum(axis=1) / den


def _hamed_rao_factor(x: np.ndarray, slope: np.ndarray, n: np.ndarray, max_lag: int | None) -> np.ndarray:
    """How much the variance of S grows because of autocorrelation (Hamed and Rao 1998)."""
    n_t = x.shape[1]
    resid = x - slope[:, None] * np.arange(n_t)
    ranks = rankdata(resid, axis=1, nan_policy="omit")
    with np.errstate(divide="ignore"):
        bound = norm.ppf(1 - ALPHA / 2) / np.sqrt(n)
    sni = np.zeros(len(x))
    for k in range(1, (max_lag or n_t - 1) + 1):
        r = _acf(ranks, k)
        keep = np.abs(r) > bound                           # only clearly non zero autocorrelation
        sni += np.where(keep, (n - k) * (n - k - 1) * (n - k - 2) * r, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return 1 + 2.0 / (n * (n - 1) * (n - 2)) * sni


def _r1_corrected(resid: np.ndarray, n: np.ndarray, bias: float = 2.0) -> np.ndarray:
    """Lag 1 autocorrelation of detrended values. Short series underestimate it, so add the known
    small sample correction (bias + 4 r) / n; only positive autocorrelation (the kind that fakes trends)
    is kept. Removing a curve (3 numbers fitted) biases r down more than a line (2), hence bias 3 there."""
    r = np.nan_to_num(_acf(resid, 1))
    with np.errstate(invalid="ignore", divide="ignore"):
        r = r + np.nan_to_num((bias + 4 * r) / n)
    return np.clip(r, 0.0, 0.9)


def _curve_resid(x: np.ndarray) -> np.ndarray:
    """What is left of each row after a quadratic curve (least squares, missing years skipped).

    The memory of the noise is measured on this, not on what is left after a straight line: a change
    that bends (flat, then rising) leaves a slow wave behind a straight line, and that wave would be
    mistaken for memory, making the test needlessly strict. See docs/DECISIONS.md (D1 update, Sat).
    """
    t = np.arange(x.shape[1], dtype=np.float64)
    t = (t - t.mean()) / max(t.std(), 1.0)
    X = np.stack([np.ones_like(t), t, t * t])                  # [3, years]
    ok = np.isfinite(x)
    y = np.where(ok, x, 0.0)
    w = ok.astype(np.float64)
    A = np.einsum("iy,jy,ny->nij", X, X, w)                    # normal equations per row
    b = np.einsum("iy,ny->ni", X, y * w)
    coef = np.einsum("nij,nj->ni", np.linalg.pinv(A), b)
    resid = x - coef @ X
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scale = np.nanmax(np.abs(x), axis=1, keepdims=True)
        tiny = np.nanmax(np.abs(resid), axis=1, keepdims=True) <= 1e-9 * np.maximum(scale, 1e-12)
    resid = np.where(tiny, 0.0, resid)                       # an exact curve: rounding noise is not memory
    return np.where(ok, resid, np.nan)


def _prewhiten(x: np.ndarray, r1: np.ndarray) -> np.ndarray:
    return x[:, 1:] - r1[:, None] * x[:, :-1]


def _chunk(x: np.ndarray, method: str, min_years: int) -> dict[str, np.ndarray]:
    s, var, slope, n = _plain(x)
    if method == "hr":
        var = var * _hamed_rao_factor(x, slope, n, None)
    elif method == "hr3":
        var = var * np.maximum(_hamed_rao_factor(x, slope, n, 3), 1.0)
    elif method == "pw":
        s, var, _, _ = _plain(_prewhiten(x, _acf(x, 1)))
    elif method == "tfpw":
        t = np.arange(x.shape[1])
        resid = x - slope[:, None] * t
        r1 = np.clip(np.nan_to_num(_acf(resid, 1)), 0.0, 0.95)   # only positive autocorrelation inflates trends
        s, var, _, _ = _plain(_prewhiten(resid, r1) + slope[:, None] * t[1:])
    elif method == "ess":
        # 20 or more years: memory measured after a curve, so a bent change is not mistaken for memory.
        # Shorter ranges: a curve leaves too few years to judge memory, so a straight line as before.
        if x.shape[1] >= CURVE_MIN_YEARS:
            r1 = _r1_corrected(_curve_resid(x), n, bias=3.0)
        else:
            r1 = _r1_corrected(x - slope[:, None] * np.arange(x.shape[1]), n)
        var = var * (1 + r1) / (1 - r1)
    elif method == "ess_line":
        r1 = _r1_corrected(x - slope[:, None] * np.arange(x.shape[1]), n)
        var = var * (1 + r1) / (1 - r1)
    elif method == "ws":
        t = np.arange(x.shape[1])
        b, w = slope, x
        for _ in range(5):                                  # slope and autocorrelation refine each other
            r1 = _r1_corrected(x - b[:, None] * t, n)
            w = _prewhiten(x, r1) / (1 - r1[:, None])
            _, _, b, _ = _plain(w)
            b = np.nan_to_num(b)
        s, var, _, _ = _plain(w)
    elif method != "mk":
        raise ValueError(f"unknown method {method}; choose from {list(METHODS)}")

    with np.errstate(invalid="ignore", divide="ignore"):
        z = (s - np.sign(s)) / np.sqrt(var)
    p = 2 * norm.sf(np.abs(z))
    p = np.where(s == 0, 1.0, p)

    # 95% range of the Sen slope (Sen 1968), using the same variance as the test.
    n_t = x.shape[1]
    i, j = np.triu_indices(n_t, 1)
    with np.errstate(invalid="ignore"):
        slopes = np.sort((x[:, j] - x[:, i]) / (j - i), axis=1)   # NaN sorts to the end
    n_pairs = np.isfinite(slopes).sum(axis=1)
    with np.errstate(invalid="ignore"):
        half = norm.ppf(1 - ALPHA / 2) * np.sqrt(var)
    half = np.where(np.isfinite(half), half, 0.0)
    last = np.maximum(n_pairs - 1, 0)
    lo_i = np.clip(np.floor((n_pairs - half) / 2).astype(int) - 1, 0, last)
    hi_i = np.clip(np.ceil((n_pairs + half) / 2).astype(int), 0, last)
    rows = np.arange(len(x))
    slope_lo, slope_hi = slopes[rows, lo_i], slopes[rows, hi_i]

    # A series that never changes is a fill value, not a measurement (soil wetness over the sea is
    # always exactly 1): no data, never "not proven".
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        flat = ~(np.nanmax(x, axis=1) - np.nanmin(x, axis=1) > 1e-9)
    bad = (n < min_years) | ~np.isfinite(p) | ~np.isfinite(slope) | flat
    out = {"slope": slope * 10, "slope_lo": slope_lo * 10, "slope_hi": slope_hi * 10, "p": p, "z": z}
    for key in out:
        out[key] = np.where(bad, np.nan, out[key])
    out["n_years"] = n.astype(np.int16)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out["mean"] = np.where(n > 0, np.nanmean(np.where(np.isfinite(x), x, np.nan), axis=1), np.nan)
    return out


def min_valid_years(n_years: int) -> int:
    """Valid years needed for a range of n_years: 80% of it (20 of the full 25)."""
    return int(np.ceil(MIN_VALID_SHARE * n_years))


def trend_grid(annual, method: str = DEFAULT_METHOD, min_years: int | None = None) -> dict[str, np.ndarray]:
    """Trend of every place at once.

    annual: yearly values, shape [..., years]; NaN = missing.
    Returns arrays shaped like annual without the year axis:
      slope, slope_lo, slope_hi   change per decade and its 95% range (real units)
      p                           chance of a trend this strong if nothing were changing
      z                           test statistic (sign = direction)
      n_years, mean               valid years and the average level
    Places with fewer than min_years valid years (default: 80% of the years given) get NaN.
    """
    a = np.asarray(annual, dtype=np.float64)
    shape = a.shape[:-1]
    x = a.reshape(-1, a.shape[-1])
    need = min_valid_years(a.shape[-1]) if min_years is None else min_years
    parts = [_chunk(x[k:k + _CHUNK], method, need) for k in range(0, len(x), _CHUNK)] or [_chunk(x, method, need)]
    return {key: np.concatenate([p[key] for p in parts]).reshape(shape) for key in parts[0]}


def fdr_bh(p) -> np.ndarray:
    """Benjamini-Hochberg q-values. Among places with q < 0.05, about 5% are expected to be false."""
    p = np.asarray(p, dtype=np.float64)
    q = np.full(p.shape, np.nan)
    ok = np.isfinite(p)
    m = int(ok.sum())
    if m == 0:
        return q
    vals = p[ok]
    order = np.argsort(vals)
    ranked = vals[order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    back = np.empty(m)
    back[order] = np.minimum(ranked, 1.0)
    q[ok] = back
    return q


def confidence_levels(q) -> np.ndarray:
    """0 = not proven, 1 = moderate evidence, 2 = strong evidence, -1 = no data."""
    q = np.asarray(q, dtype=np.float64)
    level = np.zeros(q.shape, dtype=np.int8)
    with np.errstate(invalid="ignore"):
        level[q < MODERATE] = 1
        level[q < STRONG] = 2
    level[~np.isfinite(q)] = -1
    return level


def trend_one(series, method: str = DEFAULT_METHOD) -> dict:
    """Trend of one place. series: yearly values. Returns plain Python numbers (None = no data)."""
    res = trend_grid(np.asarray(series, dtype=np.float64)[None, :], method)
    out = {k: (None if not np.isfinite(v[0]) else float(v[0])) for k, v in res.items()}
    out["n_years"] = int(res["n_years"][0])
    return out


def change_point(series, years) -> dict | None:
    """Year the level shifted (Pettitt test). None when no clear start (p >= 0.05) or too few years."""
    x = np.asarray(series, dtype=np.float64)
    yrs = np.asarray(years)[np.isfinite(x)]
    x = x[np.isfinite(x)]
    n = len(x)
    if n < max(MIN_RANGE_YEARS, min_valid_years(len(np.asarray(series)))):
        return None
    sign = np.sign(x[None, :] - x[:, None])                  # sign[i, j] = sign(x_j - x_i)
    u = np.array([sign[:t + 1, t + 1:].sum() for t in range(n - 1)])
    k = int(np.argmax(np.abs(u)))
    p = float(min(1.0, 2 * np.exp(-6.0 * u[k] ** 2 / (n ** 3 + n ** 2))))
    if p >= ALPHA:
        return None
    return {"year": int(yrs[k + 1]), "p": round(p, 4), "method": "Pettitt test"}


def direction(slope: float | None, level: int) -> str:
    if slope is None or level < 0:
        return "no data"
    if level == 0:
        return "not proven"
    return "increasing" if slope > 0 else "decreasing"
