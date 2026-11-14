import numpy as np, evalx as E, gate_strategies as G
if __name__ == "__main__":
    st = G.CropAwareGate(100, 200, 100, 250, 'exact0')
    hi = E.EG_RAIN >= 100
    for c in ['wheat', 'barley']:
        r = E._run_crop(st, c)
        k = r['eg0'][hi] >= 0.5
        print(c, 'EG cells rain>=100 scored >=.5 rain-only:', int(k.sum()), 'of', int(hi.sum()), 'rain of those:', np.round(E.EG_RAIN[hi][k]).tolist())
    print('nodes', E.count_nodes(E.final_models(st)))
