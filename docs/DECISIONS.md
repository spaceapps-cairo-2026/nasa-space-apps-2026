# Decisions (lane A keeps this current)

One line per decision: `time | decision | why | who`

- Fri | Contract-first, mock-first architecture with 3 lanes | lets 3 Claude accounts work in parallel without waiting on each other | team
- Fri | Plain HTML + Leaflet + Plotly frontend, FastAPI backend | no build step, nothing to debug at 3 AM | team
- Fri | PROJECT_PLAN.md (farming trend explorer, F0 to F6) replaces the earlier MODIS fingerprint concept; algorithms decided during the hackathon (D1 to D9) | plan agreed by the team | team
- Fri | The "Leaflet" frontend choice above is reopened by D3 (globe and map library) | the plan needs a 3D globe | team
- Fri | Trends (F1) cover the whole world as maps; farming features (F2 to F4) only for focus countries | the challenge is about Earth, and crops need per country care | Mohammed
- Fri | World trends use live fetch per region with a disk cache; the 4 hour bulk world download is optional | nobody waits for a download; demo regions are fetched beforehand | Mohammed
- Fri | D1: trend = Sen's slope on annual means, 2001 to 2025; confidence = Mann-Kendall with the variance scaled by lag 1 autocorrelation (effective sample size, small sample bias corrected); FDR (Benjamini-Hochberg) on every map | of 7 methods tested on 20,000 trendless series it is the only one that keeps false alarms near 5% (3.3 to 7.5%) and still finds real trends (32 to 65%); Hamed-Rao gave 8 to 25% false alarms, pre-whitening found only 16 to 30% of real trends. Evidence: `python ml/compare_methods.py`, table in `docs/METHODS.md` section 0 | Mohammed
- Fri | D2: three confidence levels: strong evidence (below 0.01), moderate evidence (below 0.05), not proven (the rest); applied to q on maps and to p for a single place; the exact number is always returned | matches the plan's wording rule, and "weak" levels would not be significant under rule 10 | Mohammed
- Fri | Change start year uses the Pettitt test (shown only for proven trends, p below 0.05), not ruptures PELT | no penalty to tune, gives its own p-value, instant | Mohammed
- Fri | Contract v0.3: `/api/variables`, `/api/trend/point`, `/api/trend/region`, `/api/trend/world`; shapes in `contracts/trend.schema.json`; region maps are compact grids. v0.2 PredictionBundle endpoints kept unchanged | F1 needs point and map answers; nothing existing breaks | Mohammed
