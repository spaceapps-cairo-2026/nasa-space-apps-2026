"""Prefix "gate": a transparent rain rule on top of the unchanged baseline model (tuned Extra Trees, v2 recipe).

score_shown = score_model * g_eff,   g_eff = irr_share + (1 - irr_share) * g(rain_annual)

so a place scored "irrigated" (share 1) is never touched and a place scored "rain only" (share 0) gets the full gate.
Nothing is retrained: make(), counter() and train_set() are the baseline's.
"""
import numpy as np

import evalx as E

RAIN = E.RAIN
WINTER_CEREALS = ('wheat', 'barley')
SUFFIX = {'share': '', 'exact0': '-x0'}


def linear_gate(rain, r0, r1):
    """0 below r0 mm/year, 1 above r1, straight line between."""
    return np.clip((rain - r0) / float(r1 - r0), 0.0, 1.0)


def logistic_gate(rain, mid, scale):
    """Smooth S curve: 0.5 at mid mm/year, about 0.12 at mid - 2 scale and 0.88 at mid + 2 scale."""
    return 1.0 / (1.0 + np.exp(-(rain - mid) / float(scale)))


def step_gate(rain, r):
    """Hard cut-off: 0 below r mm/year, 1 from r on."""
    return (rain >= r).astype(float)


def blend(p, Z, g, mode='share'):
    """mode 'share' (the default): g_eff = irr_share + (1 - irr_share) * g, a partly irrigated cell is partly gated.
    mode 'exact0': the gate applies only where irr_share == 0 (the app's rain-only mode); any irrigation switches it off."""
    s = np.clip(Z[:, -1], 0.0, 1.0)
    if mode == 'exact0':
        return np.where(s == 0, p * g, p)
    return p * (s + (1.0 - s) * g)


class LinearGate(E.Strategy):
    """Baseline model; rain-only score multiplied by a piecewise-linear gate (0 below r0, 1 above r1), all crops."""

    def __init__(self, r0, r1, mode='share'):
        self.r0, self.r1, self.mode = r0, r1, mode
        self.name = f"gate-lin-{r0}-{r1}" + SUFFIX[mode]

    def post(self, p, Z):
        return blend(p, Z, linear_gate(Z[:, RAIN], self.r0, self.r1), self.mode)


class LogisticGate(E.Strategy):
    """Baseline model; rain-only score multiplied by a logistic gate centred at `mid` mm/year, all crops."""

    def __init__(self, mid, scale, mode='share'):
        self.mid, self.scale, self.mode = mid, scale, mode
        self.name = f"gate-logit-{mid}-{scale}" + SUFFIX[mode]

    def post(self, p, Z):
        return blend(p, Z, logistic_gate(Z[:, RAIN], self.mid, self.scale), self.mode)


class StepGate(E.Strategy):
    """Baseline model; rain-only score set to 0 below r mm/year (hard cut-off), all crops."""

    def __init__(self, r, mode='share'):
        self.r, self.mode = r, mode
        self.name = f"gate-step-{r}" + SUFFIX[mode]

    def post(self, p, Z):
        return blend(p, Z, step_gate(Z[:, RAIN], self.r), self.mode)


class CropAwareGate(E.Strategy):
    """Baseline model; two linear gates: an early one (c0, c1) for wheat and barley (winter cereals reach furthest
    into dry land) and a later one (r0, r1) for the other 38 crops. c0 = None means no gate at all for the cereals.

    post() is not told the crop, so the crop is remembered from train_set(), which the suite calls for the same
    crop right before every prediction (one crop per worker call, sequential). The training set is untouched."""

    def __init__(self, c0, c1, r0, r1, mode='share'):
        self.c0, self.c1, self.r0, self.r1, self.mode = c0, c1, r0, r1, mode
        self.name = f"gate-crop-{'none' if c0 is None else f'{c0}-{c1}'}_{r0}-{r1}" + SUFFIX[mode]
        self._crop = None

    def train_set(self, Xtr, ytr, unf_ok, crop):
        self._crop = crop
        return super().train_set(Xtr, ytr, unf_ok, crop)

    def gate(self, rain, crop):
        if crop in WINTER_CEREALS:
            return np.ones(len(rain)) if self.c0 is None else linear_gate(rain, self.c0, self.c1)
        return linear_gate(rain, self.r0, self.r1)

    def post(self, p, Z):
        assert self._crop is not None
        return blend(p, Z, self.gate(Z[:, RAIN], self._crop), self.mode)
