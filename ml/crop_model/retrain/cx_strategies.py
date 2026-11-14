"""Approach "cx": rain-only counter-examples. Same tuned Extra Trees as the baseline; only the rows added as
'not grown at irrigation share 0' and their sample weights change. Everything comes from the training folds."""
import numpy as np

import evalx as E

H = E.H
RAIN = H.RAIN


class CX(E.Strategy):
    """Counter-example recipe with knobs.

    irr_thr       copy every training cell with irrigated share >= irr_thr to share 0, labelled not grown (v2: 0.95)
    dry_irr_thr   if set, also copy cells with irrigated share >= dry_irr_thr AND rain < dry_rain (dry cells only)
    unf_rain      unfarmed cells (< 1,000 ha) with rain < unf_rain are added as not grown at share 0 (v2: 100)
    cw            weight multiplier for counter-example rows, applied after class balancing (v2: 1)
    cw_rain       if set, only counter rows with rain < cw_rain get the multiplier (wet irrigated copies stay at 1)
    ramp          if set to (r0, r1): the multiplier is cw below r0 mm and falls linearly to 1 at r1 mm (replaces cw_rain)
    mode          'mult'   multiply and leave it (negatives become heavier than positives)
                  'renorm' multiply, then rescale all negatives so positives and negatives weigh the same again
                  'group'  counter rows as their own group: their total weight = group_frac x the total weight of
                           the positives (the real negatives keep total weight = positives)
    """

    def __init__(self, irr_thr=0.95, dry_irr_thr=None, dry_rain=250.0, unf_rain=100.0, cw=1.0, cw_rain=None,
                 mode='mult', group_frac=0.5, ramp=None):
        self.ramp = ramp
        self.irr_thr, self.dry_irr_thr, self.dry_rain = irr_thr, dry_irr_thr, dry_rain
        self.unf_rain, self.cw, self.cw_rain, self.mode, self.group_frac = unf_rain, cw, cw_rain, mode, group_frac
        self.name = (f"cx-irr{irr_thr}-dirr{dry_irr_thr}@{dry_rain:g}-unf{unf_rain:g}-w{cw:g}"
                     f"{'' if cw_rain is None else f'<{cw_rain:g}'}-{mode}")

    def make(self):
        return H.MAKERS['ET']()

    def counter(self, Xtr, unf_ok):
        m = Xtr[:, -1] >= self.irr_thr
        if self.dry_irr_thr is not None:
            m |= (Xtr[:, -1] >= self.dry_irr_thr) & (Xtr[:, RAIN] < self.dry_rain)
        Xc = Xtr[m].copy()
        Xc[:, -1] = 0.0
        return np.vstack([Xc, E.X_UNF[unf_ok & (E.UNF_RAIN < self.unf_rain)]])

    def train_set(self, Xtr, ytr, unf_ok, crop):
        k = ~np.isnan(ytr)
        Xc = self.counter(Xtr, unf_ok)
        n_real = int(k.sum())
        Xf, yf = np.vstack([Xtr[k], Xc]), np.concatenate([ytr[k], np.zeros(len(Xc))])
        is_c = np.arange(len(yf)) >= n_real
        heavy = is_c if self.cw_rain is None else is_c & (Xf[:, RAIN] < self.cw_rain)
        if self.mode == 'group':
            w = np.ones(len(yf))
            pos, neg = (yf == 1) & ~is_c, (yf == 0) & ~is_c
            if pos.any() and neg.any() and heavy.any():
                w[pos] = 1.0 / pos.sum()
                w[neg] = 1.0 / neg.sum()
                w[is_c] = 0.0
                w[heavy] = self.group_frac / heavy.sum()
                light = is_c & ~heavy                      # counter rows outside the heavy group: weigh like a real negative
                w[light] = 1.0 / neg.sum()
                w *= len(yf) / w.sum()
            else:
                w = H.bal_w(yf)
            return Xf, yf, w
        w = H.bal_w(yf)
        if self.ramp is not None:
            r0, r1 = self.ramp
            t = np.clip((r1 - Xf[:, RAIN]) / (r1 - r0), 0.0, 1.0)
            w[is_c] *= (1.0 + (self.cw - 1.0) * t)[is_c]
        else:
            w[heavy] *= self.cw
        if self.mode == 'renorm':
            pos, neg = yf == 1, yf == 0
            if pos.any():
                w[neg] *= w[pos].sum() / w[neg].sum()
        return Xf, yf, w


class CXCrop(CX):
    """CX plus a crop-aware exemption, learned from the training folds only.

    For each crop, the share of rain-fed farmland (irrigated share <= 0.2) that grows it is computed in 50 mm rain bins
    on the training folds. Where rain >= exempt_min_rain and that share is >= exempt_prev (the crop is a common
    rain-fed crop at that rainfall, e.g. wheat and barley at 150 to 300 mm), the stronger counter-examples are NOT
    applied for that crop: rows of the v2 recipe keep weight 1 and the extra rows (new unfarmed cells, new irrigated
    copies) are left out. Everywhere else the counter rows are used with the multiplier cw (below cw_rain if set).
    """

    def __init__(self, exempt_prev=0.4, exempt_min_rain=100.0, bin_mm=50.0, min_cells=20, **kw):
        super().__init__(**kw)
        self.exempt_prev, self.exempt_min_rain, self.bin_mm, self.min_cells = exempt_prev, exempt_min_rain, bin_mm, min_cells

    def _parts(self, Xtr, unf_ok):
        """counter rows and a flag: True where the row is also in the v2 recipe."""
        m = Xtr[:, -1] >= self.irr_thr
        if self.dry_irr_thr is not None:
            m |= (Xtr[:, -1] >= self.dry_irr_thr) & (Xtr[:, RAIN] < self.dry_rain)
        Xc = Xtr[m].copy()
        v2a = Xc[:, -1] >= 0.95
        Xc[:, -1] = 0.0
        u = unf_ok & (E.UNF_RAIN < self.unf_rain)
        return np.vstack([Xc, E.X_UNF[u]]), np.concatenate([v2a, E.UNF_RAIN[u] < 100.0])

    def _exempt(self, Xtr, ytr, rain):
        rf = (Xtr[:, -1] <= 0.2) & ~np.isnan(ytr)
        nb = int(400 // self.bin_mm)
        b = np.minimum((Xtr[rf, RAIN] // self.bin_mm).astype(int), nb)
        n = np.bincount(b, minlength=nb + 1)
        pos = np.bincount(b, weights=(ytr[rf] == 1).astype(float), minlength=nb + 1)
        prev = np.where(n >= self.min_cells, pos / np.maximum(n, 1), 0.0)
        prev[nb] = 0.0                                  # the open top bin (>= 400 mm) is never exempt: not a dry-margin question
        rb = np.minimum((rain // self.bin_mm).astype(int), nb)
        return (rain >= self.exempt_min_rain) & (prev[rb] >= self.exempt_prev)

    def train_set(self, Xtr, ytr, unf_ok, crop):
        k = ~np.isnan(ytr)
        Xc, v2 = self._parts(Xtr, unf_ok)
        ex = self._exempt(Xtr, ytr, Xc[:, RAIN])
        keep = ~ex | v2                                 # exempt extra rows are dropped
        Xc, ex = Xc[keep], ex[keep]
        n_real = int(k.sum())
        Xf, yf = np.vstack([Xtr[k], Xc]), np.concatenate([ytr[k], np.zeros(len(Xc))])
        w = H.bal_w(yf)
        heavy = ~ex if self.cw_rain is None else ~ex & (Xc[:, RAIN] < self.cw_rain)
        mult = np.ones(len(Xc))
        if self.ramp is not None:
            r0, r1 = self.ramp
            mult = 1.0 + (self.cw - 1.0) * np.clip((r1 - Xc[:, RAIN]) / (r1 - r0), 0.0, 1.0)
            mult[ex] = 1.0
        else:
            mult[heavy] = self.cw
        w[n_real:] *= mult
        return Xf, yf, w
