"""Approach "lab": repair the noisy "rain-fed" labels of desert farmland (training rows only).

Hypothesis: below R mm of rain a year no crop grows on rain; what MapSPAM calls rain-fed there runs on supplied
water (groundwater, spate, flood recession). Held-out cells are never touched: only the training rows change.
"""
import numpy as np

import evalx as E
import harness as H

RAIN = H.RAIN


class LabRepair(E.Strategy):
    """Tuned Extra Trees + a repair of dry training cells.

    mode:
      'none'   the v2 recipe unchanged
      'irr1'   training farmland with rain < R gets irr_share = 1 (its water is supplied)
      'soft'   irr_share := max(irr_share, ramp), ramp = 1 at rain <= lo, falling linearly to 0 at rain >= hi
      'drop'   positives of training cells with rain < R and irr_share < 0.5 are removed (label unknown)
      'dropcc' as 'drop', and every training cell with rain < R is also copied at share 0 as 'not grown'
    v2_irr:   keep the v2 counter-examples "copy of every cell >= 95% irrigated at share 0" (computed AFTER the repair,
              so with 'irr1'/'soft' the repaired dry cells are counter-examples too). If False, only the repaired
              dry cells (share raised to >= 0.95 by the repair) are copied.
    unf_rain: unfarmed cells with less rain than this are 'not grown' counter-examples (v2: 100; 0 = none).
    cw:       weight multiplier of the counter-example rows after class balancing (1 = v2).
    """

    def __init__(self, mode='none', R=None, lo=None, hi=None, v2_irr=True, unf_rain=100, cw=1.0):
        self.mode, self.R, self.lo, self.hi, self.v2_irr, self.unf_rain, self.cw = mode, R, lo, hi, v2_irr, unf_rain, cw
        self.name = f"{mode}-R{R}-lo{lo}-hi{hi}-v2{int(v2_irr)}-unf{unf_rain}-cw{cw}"

    def repair(self, Xtr, ytr):
        """-> repaired copies of X and y, and the mask of cells whose share the repair raised to >= 0.95."""
        X2, y2 = Xtr.copy(), ytr.copy()
        rain = X2[:, RAIN]
        fixed = np.zeros(len(X2), bool)
        if self.mode == 'irr1':
            fixed = rain < self.R
            X2[fixed, -1] = 1.0
        elif self.mode == 'soft':
            ramp = np.clip((self.hi - rain) / (self.hi - self.lo), 0.0, 1.0)
            fixed = (ramp >= 0.95)
            X2[:, -1] = np.maximum(X2[:, -1], ramp)
        elif self.mode in ('drop', 'dropcc'):
            dry = rain < self.R
            y2[dry & (X2[:, -1] < 0.5) & (y2 == 1)] = np.nan
            if self.mode == 'dropcc':
                fixed = dry
        return X2, y2, fixed

    def counter_rows(self, X2, fixed, unf_ok):
        m = fixed.copy()
        if self.v2_irr:
            m |= X2[:, -1] >= 0.95
        Xc = X2[m].copy()
        Xc[:, -1] = 0.0
        if self.unf_rain:
            Xc = np.vstack([Xc, E.X_UNF[unf_ok & (E.UNF_RAIN < self.unf_rain)]])
        return Xc

    def train_set(self, Xtr, ytr, unf_ok, crop):
        X2, y2, fixed = self.repair(Xtr, ytr)
        k = ~np.isnan(y2)
        Xc = self.counter_rows(X2, fixed, unf_ok)
        Xf, yf = np.vstack([X2[k], Xc]), np.concatenate([y2[k], np.zeros(len(Xc))])
        w = H.bal_w(yf)
        if self.cw != 1.0 and len(Xc):
            w[k.sum():] *= self.cw
        return Xf, yf, w


VARIANTS = {
    # sanity: must reproduce the baseline
    'lab-none': dict(mode='none'),
    # (i) irr_share := 1 below R, together with the v2 counter-examples
    'lab-irr1-R50': dict(mode='irr1', R=50),
    'lab-irr1-R75': dict(mode='irr1', R=75),
    'lab-irr1-R100': dict(mode='irr1', R=100),
    'lab-irr1-R125': dict(mode='irr1', R=125),
    'lab-irr1-R150': dict(mode='irr1', R=150),
    'lab-irr1-R200': dict(mode='irr1', R=200),
    # (i) replacing the v2 irrigated copies (only the repaired dry cells are copied; deserts kept)
    'lab-irr1-R100-repl': dict(mode='irr1', R=100, v2_irr=False),
    'lab-irr1-R150-repl': dict(mode='irr1', R=150, v2_irr=False),
    'lab-irr1-R200-repl': dict(mode='irr1', R=200, v2_irr=False),
    # (i) replacing ALL v2 counter-examples (no unfarmed deserts either)
    'lab-irr1-R150-replall': dict(mode='irr1', R=150, v2_irr=False, unf_rain=0),
    # (ii) drop the dry cells' rain-fed positives
    'lab-drop-R100': dict(mode='drop', R=100),
    'lab-drop-R150': dict(mode='drop', R=150),
    'lab-drop-R200': dict(mode='drop', R=200),
    'lab-dropcc-R150': dict(mode='dropcc', R=150),
    # (iii) soft ramp
    'lab-soft-50-150': dict(mode='soft', lo=50, hi=150),
    'lab-soft-100-200': dict(mode='soft', lo=100, hi=200),
    'lab-soft-75-250': dict(mode='soft', lo=75, hi=250),
    'lab-soft-100-300': dict(mode='soft', lo=100, hi=300),
    # follow-ups: the same hypothesis applied to unfarmed land too (unfarmed cells below R are counter-examples)
    'lab-irr1-R150-unf150': dict(mode='irr1', R=150, unf_rain=150),
    'lab-irr1-R200-unf200': dict(mode='irr1', R=200, unf_rain=200),
    'lab-irr1-R125-unf125': dict(mode='irr1', R=125, unf_rain=125),
    'lab-soft-100-200-unf150': dict(mode='soft', lo=100, hi=200, unf_rain=150),
    'lab-soft-100-200-unf200': dict(mode='soft', lo=100, hi=200, unf_rain=200),
    'lab-soft-100-250': dict(mode='soft', lo=100, hi=250),
    'lab-soft-100-250-unf200': dict(mode='soft', lo=100, hi=250, unf_rain=200),
    'lab-soft-100-250-unf250': dict(mode='soft', lo=100, hi=250, unf_rain=250),
    'lab-soft-100-200-unf250': dict(mode='soft', lo=100, hi=200, unf_rain=250),
    'lab-irr1-R150-unf200': dict(mode='irr1', R=150, unf_rain=200),
    'lab-irr1-R150-unf250': dict(mode='irr1', R=150, unf_rain=250),
    'lab-none-unf200': dict(mode='none', unf_rain=200),
    'lab-none-unf250': dict(mode='none', unf_rain=250),
    # second round: drop + copy (the only family that kept the Egypt irrigated-mode AUC)
    'lab-dropcc-R100': dict(mode='dropcc', R=100),
    'lab-dropcc-R125': dict(mode='dropcc', R=125),
    'lab-dropcc-R175': dict(mode='dropcc', R=175),
    'lab-dropcc-R200': dict(mode='dropcc', R=200),
    'lab-dropcc-R150-repl': dict(mode='dropcc', R=150, v2_irr=False),
    'lab-dropcc-R150-replall': dict(mode='dropcc', R=150, v2_irr=False, unf_rain=0),
    'lab-dropcc-R125-unf125': dict(mode='dropcc', R=125, unf_rain=125),
    'lab-dropcc-R150-unf150': dict(mode='dropcc', R=150, unf_rain=150),
    'lab-dropcc-R175-unf175': dict(mode='dropcc', R=175, unf_rain=175),
    'lab-dropcc-R200-unf200': dict(mode='dropcc', R=200, unf_rain=200),
    'lab-dropcc-R150-unf200': dict(mode='dropcc', R=150, unf_rain=200),
    'lab-dropcc-R150-cw2': dict(mode='dropcc', R=150, cw=2.0),
    'lab-dropcc-R150-unf150-cw2': dict(mode='dropcc', R=150, unf_rain=150, cw=2.0),
    'lab-dropcc-R125-unf150': dict(mode='dropcc', R=125, unf_rain=150),
    'lab-dropcc-R125-unf200': dict(mode='dropcc', R=125, unf_rain=200),
    'lab-dropcc-R100-unf150': dict(mode='dropcc', R=100, unf_rain=150),
    'lab-dropcc-R100-unf200': dict(mode='dropcc', R=100, unf_rain=200),
    'lab-dropcc-R175-unf150': dict(mode='dropcc', R=175, unf_rain=150),
    # counter-examples weighted up
    'lab-irr1-R150-cw3': dict(mode='irr1', R=150, cw=3.0),
    'lab-irr1-R150-unf150-cw3': dict(mode='irr1', R=150, unf_rain=150, cw=3.0),
    'lab-soft-100-200-unf200-cw3': dict(mode='soft', lo=100, hi=200, unf_rain=200, cw=3.0),
}


def get(name):
    return LabRepair(**VARIANTS[name])
