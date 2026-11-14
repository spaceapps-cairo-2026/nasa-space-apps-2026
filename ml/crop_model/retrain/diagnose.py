"""Why does rain-only mode give false alarms in Egypt? Look at the training data and the deployed model."""
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"C:/Users/mada_/AppData/Local/Temp/claude/21b1564fbae470c5/cda8a06c-064b-4638-b877-2536737f8d60/scratchpad/train")
import harness as H

pd.set_option("display.width", 250)
farm, cells = H.farm, H.cells_all

print("== 1. Rain-fed farming in the training table by rain band (farmland cells, share of harvested area that is rain-fed)")
bands = [0, 50, 100, 150, 200, 250, 300, 400, 600, 1e9]
farm["band"] = pd.cut(farm.rain_annual, bands, right=False)
farm["rf_share"] = 1 - farm.irr_share
g = farm.groupby("band", observed=True)
print(pd.DataFrame({"cells": g.size(), "mean irr_share": g.irr_share.mean().round(2), "cells irr>=.95": g.apply(lambda d: (d.irr_share >= .95).sum()),
                    "cells irr<=.2": g.apply(lambda d: (d.irr_share <= .2).sum()), "rain-fed ha (M)": g.TR_total.sum().div(1e6).round(2),
                    "irrigated ha (M)": g.TI_total.sum().div(1e6).round(2)}))

print("\n== 2. Rain-fed dominant cells (irr<=.2) under 150 mm: where are they, what do they grow (rain-fed area)")
d = farm[(farm.irr_share <= .2) & (farm.rain_annual < 150)]
print(len(d), "cells;", d.country.value_counts().head(15).to_dict())
tr = {H.CROP_NAMES[c]: d["TR_" + c].sum() for c in H.CODES}
print("top rain-fed crops (ha):", {k: int(v) for k, v in sorted(tr.items(), key=lambda kv: -kv[1])[:10]})

print("\n== 3. Unfarmed cells (TA<1000 ha) in the table by rain band = possible counter-examples")
un = cells[cells.TA_total < 1000].copy()
un["band"] = pd.cut(un.rain_annual, bands, right=False)
print(un.groupby("band", observed=True).size().to_dict())
print("unfarmed cells that have NO rows in the table at all are missing (the table only holds cells with some MapSPAM area).")

print("\n== 4. Egypt cells with rain-only scores >= 50 in the app file, joined to the training table")
o = json.load(open(r"D:/nasa_space_apps/ml/outputs/farming_EGY.json", encoding="utf-8"))
gr = o["grid"]
ids = [c["id"] for c in o["crops"]]
key = {(round(float(a), 3), round(float(b), 3)): i for i, (a, b) in enumerate(zip(cells.lat, cells.lon))}
rows = []
for k, ch in enumerate(o["inside"]):
    if ch != "1":
        continue
    i, j = divmod(k, gr["ncols"])
    lat, lon = gr["lat0"] + i * gr["dlat"], gr["lon0"] + j * gr["dlon"]
    hit = [c for c in ids if (o["suitability"]["rainfed"][c][0][k] or 0) >= 50]
    if not hit:
        continue
    t = cells.iloc[key[(round(lat, 3), round(lon, 3))]] if (round(lat, 3), round(lon, 3)) in key else None
    rows.append({"lat": lat, "lon": lon, "rain": o["rain_now_mm"][k], "n": len(hit), "crops": ",".join(hit)[:70],
                 "in_table": t is not None, "TA_ha": None if t is None else round(float(t.TA_total)),
                 "irr_share": None if t is None else round(float(t.TI_total / max(t.TA_total, 1)), 2),
                 "rh": None if t is None else round(float(t.rh_mean), 1), "gwetroot": None if t is None else round(float(t.soil_root_wetness), 2),
                 "t_mean": None if t is None else round(float(t.t_mean), 1)})
fa = pd.DataFrame(rows).sort_values(["rain", "lat"])
print(fa.to_string(index=False))
print("\ncells:", len(fa), "| in table:", int(fa.in_table.sum()), "| farmland (>=1000 ha):", int((fa.TA_ha >= 1000).sum()),
      "| of those irr>=.95:", int(((fa.TA_ha >= 1000) & (fa.irr_share >= .95)).sum()),
      "| irr .8-.95:", int(((fa.TA_ha >= 1000) & (fa.irr_share >= .8) & (fa.irr_share < .95)).sum()))

print("\n== 5. Egypt farmland cells: irrigated share distribution")
eg = farm[farm.country == "Egypt"]
print(pd.cut(eg.irr_share, [0, .2, .5, .8, .9, .95, .99, 1.01], right=False).value_counts().sort_index().to_dict())
print("Egypt farmland with rain>=100:", int((eg.rain_annual >= 100).sum()), "| irr<.95 among them:", int(((eg.rain_annual >= 100) & (eg.irr_share < .95)).sum()))
print(eg[(eg.irr_share < .95)][["lat", "lon", "rain_annual", "irr_share", "TA_total", "TR_total"]].round(2).sort_values("irr_share").head(25).to_string(index=False))

print("\n== 6. World: farmland cells with rain < 250 mm whose climate is like Egypt's north coast (t_mean 18-23, rain 100-250): labels at rain-fed share")
nc = farm[(farm.rain_annual.between(100, 250)) & (farm.t_mean.between(17, 24))]
print(len(nc), "cells;", nc.country.value_counts().head(12).to_dict(), "| mean irr_share", round(nc.irr_share.mean(), 2), "| irr<=.2:", int((nc.irr_share <= .2).sum()))
rfd = nc[nc.irr_share <= .2]
tot = np.maximum(rfd.TA_total, 1)
pres = {H.CROP_NAMES[c]: int(((rfd["TA_" + c] / tot) >= .02).sum()) for c in H.CODES}
print("crops present (>=2% share) in the rain-fed dominant ones:", {k: v for k, v in sorted(pres.items(), key=lambda kv: -kv[1])[:14]})
