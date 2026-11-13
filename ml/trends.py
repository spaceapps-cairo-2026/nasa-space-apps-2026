"""Lane A: the trend engine. BUILD FROM SAT 09:00. Full spec: docs/METHODS.md sections 1 to 5.

Input : data/processed/power_monthly.parquet (all Egypt, 0.5 deg)  [ready now]
        data/processed/modis_<area>.parquet (1 km pixels)          [after AppEEARS lands]
Output: ml/outputs/predictions.json  (must pass contracts/prediction.schema.json v0.2)

Functions to implement (keep these names so tests and the app stay stable):
"""
from __future__ import annotations


def annual_means(df, min_months: int = 9):
    """Monthly long table -> one value per (place, variable, year); years with < min_months valid are NaN."""
    raise NotImplementedError


def trend_one(series) -> dict:
    """Sen slope per decade, Yue-Wang Mann-Kendall p, plain MK p, direction. Uses pymannkendall."""
    raise NotImplementedError


def add_fdr(results: list[dict]) -> list[dict]:
    """Benjamini-Hochberg q per variable map (statsmodels multipletests, method='fdr_bh')."""
    raise NotImplementedError


def change_point(series):
    """Year where level/slope changes (ruptures PELT), or None if not clearly significant."""
    raise NotImplementedError


def sentence(item: dict) -> str:
    """Plain language summary using ONLY the computed numbers (template, see METHODS.md section 8)."""
    raise NotImplementedError


def main() -> None:
    """Load data -> annual means -> trend_one per place/variable -> add_fdr -> change_point -> write bundle."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
