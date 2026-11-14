"""Prints the table of all gate variants + baseline and checks the guardrails."""
import json
from pathlib import Path

R = Path(__file__).resolve().parent / "results"
B = json.loads((R / "baseline-ET-v2recipe.json").read_text())['metrics']
COLS = ['AUC', 'AUC irr', 'AUC rf', 'TSS', 'Brier', 'ECE', 'FA dry-irr', 'FA desert', 'FA semi-irr', 'FA unf100-250', 'crops/cell desert',
        'crops/cell semi-irr', 'crops/cell unf100-250', 'dry RF recall', 'dry RF recall cereals', 'EG cell AUC', 'EG FAO AUC',
        'EG rf crops<100', 'EG rf crops>=100', 'EG rf crops unfarmed', 'EG irr fits']
SHORT = ['AUC', 'AUCirr', 'AUCrf', 'TSS', 'Brier', 'ECE', 'FAdirr', 'FAdes', 'FAsemi', 'FAunf', 'c/des', 'c/semi', 'c/unf', 'dryRec', 'dryCer',
         'EGcell', 'EGfao', 'EG<100', 'EG>=100', 'EGunf', 'EGirr']


def guard(m):
    bad = []
    if m['AUC'] < B['AUC'] - 0.005: bad.append('AUC')
    if m['AUC irr'] < B['AUC irr'] - 0.005: bad.append('AUCirr')
    if m['TSS'] < B['TSS'] - 0.01: bad.append('TSS')
    if m['Brier'] > B['Brier'] + 0.01: bad.append('Brier')
    if m['dry RF recall cereals'] < 0.70: bad.append('dryCer')
    if m['EG cell AUC'] < B['EG cell AUC'] - 0.015: bad.append('EGcell')
    if m['EG FAO AUC'] < B['EG FAO AUC'] - 0.015: bad.append('EGfao')
    if abs(m['EG irr fits'] - B['EG irr fits']) > 1.5: bad.append('EGirr')
    return bad


print(f"{'name':30s} " + " ".join(f"{s:>7s}" for s in SHORT) + "  guardrails")
for p in [R / "baseline-ET-v2recipe.json"] + sorted(R.glob("gate-*.json")):
    d = json.loads(p.read_text())
    m = d['metrics']
    bad = guard(m)
    print(f"{d['name']:30s} " + " ".join(f"{m[c]:7.4f}" if m[c] < 10 else f"{m[c]:7.2f}" for c in COLS) + "  " + ("PASS" if not bad else "FAIL " + ",".join(bad)))
