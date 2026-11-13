"""Lane A: the AI part, trend fingerprints. BUILD FROM SAT ~16:00. Spec: docs/METHODS.md section 6.

Idea: every 1 km pixel gets a small vector of its trends
    [NDVI slope, LST slope, NDVI change point year, LST change point year, baseline NDVI]
A Gaussian mixture model groups pixels with similar vectors. Groups get human names from
their centers ("new farmland": NDVI up + LST down; "urban sprawl": NDVI down + LST up).
This is how the tool FINDS "opposite trends driven by the same process" automatically.
"""
from __future__ import annotations


def build_features(trend_items: list[dict]):
    """Pivot trend results per pixel into the feature matrix (standardized z-scores)."""
    raise NotImplementedError


def fit_clusters(X, k_range=range(2, 8)):
    """sklearn GaussianMixture for each k, choose k by lowest BIC. Return model + labels."""
    raise NotImplementedError


def name_clusters(model, feature_names) -> dict[int, str]:
    """Map cluster id -> human name using the sign of each center's NDVI and LST slope."""
    raise NotImplementedError


def explain(x, model, label) -> list[dict]:
    """Per-feature contribution: how much each feature pulls the pixel toward its cluster center."""
    raise NotImplementedError
