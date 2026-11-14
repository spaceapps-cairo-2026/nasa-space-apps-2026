"""Run named fam configurations:  python fam_run.py NAME [NAME ...]   (skips ones already in results/)
     python fam_run.py --table      prints all fam results;   python fam_run.py --nodes NAME ...   counts nodes."""
import json
import sys

import pandas as pd

import evalx as E
from fam_strategies import CONFIGS

COLS = ['AUC', 'AUC irr', 'AUC rf', 'TSS', 'Brier', 'ECE', 'worst AUC', 'FA dry-irr', 'FA desert', 'crops/cell desert',
        'crops/cell semi-irr', 'crops/cell unf100-250', 'dry RF recall', 'dry RF recall cereals', 'EG cell AUC', 'EG FAO AUC',
        'EG FAO TSS', 'EG rf crops<100', 'EG rf crops>=100', 'EG rf crops unfarmed', 'EG irr fits', 'seconds']

if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == '--table':
        t = E.table()
        t = t[[i.startswith('fam-') or i.startswith('baseline') for i in t.index]][COLS]
        pd.set_option('display.width', 400, 'display.max_columns', 50, 'display.max_rows', 200)
        print(t.round(4).to_string())
    elif args and args[0] == '--nodes':
        for n in args[1:]:
            print(n, 'nodes', E.count_nodes(E.final_models(CONFIGS[n])), flush=True)
    else:
        for n in args:
            if (E.RESULTS / f"fam-{n}.json").exists():
                print('skip', n)
                continue
            E.run(CONFIGS[n], f"fam-{n}")
            sys.stdout.flush()
