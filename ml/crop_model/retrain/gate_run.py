"""Runs gate variants. usage: python gate_run.py [set ...]   sets: lin logit step crop crop2"""
import json
import sys

import evalx as E
import gate_strategies as G

SETS = {
    'lin': [G.LinearGate(a, b) for a, b in [(50, 150), (75, 150), (100, 200), (100, 250), (150, 250), (150, 300), (200, 300), (200, 350)]],
    'logit': [G.LogisticGate(m, s) for m, s in [(100, 20), (150, 25), (200, 25), (250, 25)]],
    'step': [G.StepGate(r) for r in (100, 150, 200, 250)],
    'crop': [G.CropAwareGate(*a) for a in [(50, 150, 150, 300), (50, 150, 200, 350), (100, 200, 200, 350), (75, 150, 200, 300),
                                           (None, None, 200, 350), (50, 150, 250, 400)]],
    'x0': [G.StepGate(100, 'exact0'), G.LinearGate(100, 200, 'exact0'), G.LinearGate(150, 250, 'exact0'), G.LogisticGate(150, 25, 'exact0'),
           G.CropAwareGate(100, 200, 150, 300, 'exact0'), G.CropAwareGate(100, 200, 200, 350, 'exact0'),
           G.CropAwareGate(50, 150, 200, 350, 'exact0')],
    'x0b': [G.LinearGate(100, 250, 'exact0'), G.CropAwareGate(100, 200, 100, 250, 'exact0'), G.CropAwareGate(100, 200, 150, 250, 'exact0'),
            G.CropAwareGate(100, 200, 100, 300, 'exact0'), G.CropAwareGate(50, 150, 100, 250, 'exact0')],
}

if __name__ == "__main__":
    which = sys.argv[1:] or list(SETS)
    for s in which:
        for st in SETS[s]:
            if (E.RESULTS / f"{st.name}.json").exists():
                E.show(st.name, json.loads((E.RESULTS / f"{st.name}.json").read_text())['metrics'])
                continue
            E.run(st, st.name)
