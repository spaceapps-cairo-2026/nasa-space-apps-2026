"""Print the table of all cx variants (+ baseline) with guardrail verdicts."""
import json
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parent / "results"
COLS = {'AUC': 'AUC', 'AUC irr': 'irr', 'AUC rf': 'rf', 'TSS': 'TSS', 'Brier': 'Brier', 'FA dry-irr': 'FAdi', 'FA desert': 'FAde',
        'crops/cell desert': 'c/des', 'crops/cell semi-irr': 'c/semi', 'crops/cell unf100-250': 'c/unf', 'dry RF recall': 'dRF',
        'dry RF recall cereals': 'dRFcer', 'EG cell AUC': 'EGc', 'EG FAO AUC': 'EGfao', 'EG FAO TSS': 'EGtss', 'EG rf crops<100': 'EG<100',
        'EG rf crops>=100': 'EG>=100', 'EG rf crops unfarmed': 'EGunf', 'EG irr fits': 'EGfits', 'worst AUC': 'worst', 'ECE': 'ECE'}


def guard(m, b):
    bad = []
    if m['AUC'] < b['AUC'] - 0.005: bad.append('AUC')
    if m['AUC irr'] < b['AUC irr'] - 0.005: bad.append('AUCirr')
    if m['TSS'] < b['TSS'] - 0.01: bad.append('TSS')
    if m['Brier'] > b['Brier'] + 0.01: bad.append('Brier')
    if m['dry RF recall cereals'] < 0.70: bad.append('cereals')
    if m['EG cell AUC'] < b['EG cell AUC'] - 0.015: bad.append('EGcell')
    if m['EG FAO AUC'] < b['EG FAO AUC'] - 0.015: bad.append('EGfao')
    if abs(m['EG irr fits'] - b['EG irr fits']) > 1.5: bad.append('EGfits')
    return 'ok' if not bad else 'FAIL:' + ','.join(bad)


if __name__ == "__main__":
    b = json.loads((R / "baseline-ET-v2recipe.json").read_text())['metrics']
    rows = {'baseline': {**{v: b[k] for k, v in COLS.items()}, 'guard': '-'}}
    for p in sorted(R.glob("cx-*.json")):
        d = json.loads(p.read_text())
        m = d['metrics']
        rows[d['name']] = {**{v: m[k] for k, v in COLS.items()}, 'guard': guard(m, b)}
    pd.set_option("display.width", 400, "display.max_rows", 200, "display.max_columns", 40)
    df = pd.DataFrame(rows).T
    for c in df.columns[:-1]:
        df[c] = df[c].astype(float).round(3 if c.startswith(('c/', 'EG<', 'EG>', 'EGu', 'EGfi', 'dRF', 'EGt')) else 4)
    print(df.to_string())
