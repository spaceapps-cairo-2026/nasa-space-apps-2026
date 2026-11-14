"""Run lab variants: python lab_run.py name1 name2 ...   (skips variants whose results/<name>.json exists)."""
import sys

import evalx as E
import lab_strategies as L

if __name__ == "__main__":
    for name in sys.argv[1:]:
        if (E.RESULTS / f"{name}.json").exists():
            print("skip", name)
            continue
        E.run(L.get(name), name)
        sys.stdout.flush()
