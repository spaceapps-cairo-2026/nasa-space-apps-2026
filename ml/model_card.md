# Model card: CropShift Earth crop-suitability model (crop-suitability-v3.1)

**Versions.** v2 was trained with Manus in a Kaggle-style notebook. v3.1, the one the app uses, is v2 retrained in this repo (`ml/crop_model/retrain/`) with the same algorithm, settings and data, to remove rain-only false alarms. Sections below describe v2's design. The v3 changes and their numbers are in the v3 section.

**Task.** For any place on land, estimate for each of 40 crops how typical the local climate is of places where that crop is grown today. The output is a suitability value from 0 to 1, in irrigated mode (water supplied) or rain-fed mode. It is applied to NASA POWER for now, +5 and +10 years if current trends continue.

**Inputs.** 10 climate features from all six NASA POWER measurements (T2M, T2M_MAX, PRECTOTCORR, RH2M, GWETTOP, GWETROOT): annual mean, coldest-month and warmest-month temperature; hottest monthly maximum; annual rainfall and its seasonality; mean humidity; surface and root-zone soil wetness (mean and driest month). One more input is the irrigation share: 1 in irrigated mode, 0 in rain-fed mode, anything in between from the app's slider.

**Training data.** IFPRI MapSPAM 2020 v2r2 harvested area (Harvard Dataverse doi:10.7910/DVN/SWPENT, CC BY 4.0), summed onto the NASA POWER grid (0.5 x 0.625 deg): 22,450 farmland cells (>= 1,000 ha harvested) on every continent. Labels: crop present if it covers >= 2% of the cell's harvested area, absent if <= 0.2%, otherwise left out. Features are the 2001 to 2025 averages from the NASA POWER archive. These match our Kaggle dataset for Egypt (largest difference per unit: °C: 0.0072; mm/year: 0.096; 0-1: 0.02; %: 0.0015). *This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no responsibility for the analyses or interpretations of the data presented here.*

**Method.** One XGBoost classifier per crop (n_estimators=200, learning_rate=0.03, max_depth=6, subsample=0.8, colsample_bytree=1.0, reg_lambda=20, min_child_weight=1), class-balanced weights, so 0.5 means the climate is as typical of cells that grow the crop as of cells that do not. The design (irrigation share as an input, share-based labels, rain-fed counter-examples) was chosen from 5 designs (one of them rain-fed only), plus an ablation without counter-examples (rain-fed false alarms on dry irrigated cells 0.09 without vs 0.00 with; on unfarmed deserts 0.10 vs 0.01). Counter-examples, all with irrigation share 0 and the label "not grown": (1) every training cell that is >= 95% irrigated, added once more, because MapSPAM shows no rain-fed farming there; (2) 1,145 unfarmed desert cells (< 100 mm rain, < 1,000 ha farmed). Without them, rain-fed mode rated desert cells suitable. The algorithm was chosen from 8 classical ML families by 5-fold spatial block cross-validation (10 x 10 deg blocks). The three best families were tuned by random search on the class-balanced Brier score, under a size budget of 2,000,000 tree nodes so the model runs in the app. XGBoost had the best mean rank over the 7 cross-validation metrics (best on: AUC, AUC irrigated farmland, AUC rain-fed farmland, Rain-fed false alarms (dry irrigated cells), Rain-fed false alarms (unfarmed deserts), worst-crop AUC); the runners-up are within 0.009 AUC. v2's trees are packed into `crop_suitability_v2.npz` (5.5 MB, 8,000 trees) and evaluated with numpy only. They reproduce the library model to 3.6e-07.

**v3 changes.** (1) Stronger rain-only counter-examples. Unfarmed land up to 250 mm of rain a year (v2: 100 mm) is taught as "not grown on rain alone", and dry counter rows count 3 times. The exception is a crop in the 50 mm rain bands where the training data shows it is a common rain-fed crop (at least 25% of rain-fed farmland there), such as wheat and barley from 100 to 400 mm. (2) A documented rain gate in rain-only mode. The score is multiplied by 0 below 100 mm, rising in a straight line to 1 at 200 mm for wheat and barley and at 250 mm for other crops, because farming on rain alone needs about 200 to 250 mm. Irrigated scores are never changed. Why: MapSPAM labels some desert farming on groundwater, spate floods or flood recession as rain-fed (303 rain-fed-dominant cells under 150 mm in Sudan, Niger, Saudi Arabia, Yemen and Iraq), so v2 learned "rain-fed crops in deserts". About 170 variants were compared on one fixed held-out suite (`retrain/evalx.py`). The choice used held-out regions and a model trained without Egypt, never Egypt itself. The runtime reproduces the XGBoost models to 3e-7 (`crop_suitability_v3.npz`, 5.5 MB, 8,000 trees, `crop_engine_v3.py`).

**v3 vs v2 on the same held-out suite (5 folds of 10 x 10 degree blocks, mean over 40 crops).**
| Check | v2 recipe | v3 |
|---|---|---|
| AUC all farmland / irrigated / rain-fed | 0.904 / 0.822 / 0.888 | 0.898 / 0.824 / 0.876 |
| TSS / Brier / ECE | 0.633 / 0.131 / 0.061 | 0.632 / 0.134 / 0.059 |
| Worst crop AUC | 0.830 | 0.791 (small millets) |
| Rain only, crops per place rated suitable: unfarmed deserts (< 100 mm) | 0.40 | 0 |
| ... farmland >= 95% irrigated with 100 to 250 mm | 2.78 | 0.52 |
| ... unfarmed land with 100 to 250 mm | 2.72 | 0.67 |
| Real rain-fed crops found at 150 to 300 mm (all crops / wheat and barley) | 0.48 / 0.76 | 0.38 / 0.75 |
| Leave-Egypt-out: AUC over Egypt's crop x cell pairs / FAOSTAT AUC | 0.851 / 0.917 | 0.862 / 0.933 |
| Leave-Egypt-out: rain-only crops per Egyptian farmland cell, < 100 mm / >= 100 mm | 0.37 / 3.73 | 0 / 0.36 |

Deployed v3 on Egypt: Cairo irrigated tomato 0.977, wheat 0.973, onion 0.968, 13 of 40 crops fit. Rain only, no crop reaches 50 below 100 mm. Above 100 mm only barley does, on the north-west coast and in North Sinai, where Egypt grows it on rain. The price is caution at the dry margin: about a fifth of the real rain-fed crops found at 150 to 300 mm by v2 now score under 50.

**v3.1 change: labels for crops grown at scale in big cells.** v2 and v3 counted a crop as grown only where it covered at least 2% of a cell's harvested area. Egypt's Nile cells are huge (up to 340,000 ha), so crops Egypt grows on tens of thousands of hectares were labelled "not grown" in almost every Egyptian cell. Sweet potato, for example, has 16,600 ha in MapSPAM and was "not grown" in 110 of 116 farmed cells. Worldwide its "grown" cells are humid tropics (median 1,290 mm of rain), so the model scored it near 0 in the Delta, where Egypt grows it. v3.1 also counts a crop as grown where the cell has at least 500 ha of it ("absent" now needs <= 0.2% and < 100 ha). 500 ha was chosen over 1,000 and 2,000 ha on the held-out suite.

| Check, held-out | v3 | v3.1 |
|---|---|---|
| AUC all / irrigated / rain-fed farmland (each against its own labels) | 0.898 / 0.824 / 0.876 | 0.899 / 0.847 / 0.880 |
| TSS / Brier / ECE | 0.632 / 0.134 / 0.059 | 0.637 / 0.129 / 0.040 |
| Worst crop AUC | 0.791 | 0.821 (tropical fruit) |
| Rain only, crops per place: deserts / irrigated 100-250 mm / unfarmed 100-250 mm | 0 / 0.52 / 0.67 | 0 / 0.50 / 0.63 |
| Leave-Egypt-out FAOSTAT AUC (label independent) | 0.933 | 0.930 |

Deployed fit, irrigated score where Egypt grows the crop (area weighted), v3 to v3.1: sweet potato 18 to 69, beans 27 to 69, sesame 33 to 70, banana 26 to 75, groundnut 49 to 68, barley 38 to 54. Major crops barely move: wheat 95 to 94, maize 79, rice 73 to 75, tomato 96 to 90. No crop that Egypt grows on less than 1,000 ha reaches 50 anywhere in Egypt. Still low: soybean (27) and sunflower (33). Egypt grows them on only 13,000 and 7,600 ha, too spread out to reach 500 ha in a cell. The app says so in its score note. Comparability: AUC, recall and the Egypt cell AUC are measured against each version's own labels. Brier, ECE, false alarms and FAOSTAT do not depend on the labels.

**Projections (Sat 14 Nov).** Only the four temperature features carry their 2001 to 2025 trend to 2030 and 2035. Rain, rain seasonality, humidity and soil wetness are held at their 2001 to 2025 average, because their NASA POWER records break around 2015 over Egypt (an independent record, ERA5, does not show the jump; docs/DECISIONS.md). Future changes in the app therefore come from the measured warming only.

**v2 performance (held-out, spatial cross-validation in the notebook, mean over 40 crops).**
| Check | Result |
|---|---|
| AUC, all farmland / irrigated farmland (share = 1) / rain-fed farmland (share = 0) | 0.904 / 0.823 / 0.888 |
| Worst crop AUC | 0.830 (tomato) |
| TSS at 0.5 / class-balanced Brier / calibration error (ECE) | 0.633 / 0.132 / 0.061 |
| Rain-fed false alarms: share of crops rated suitable in rain-fed mode on held-out farmland >= 95% irrigated with < 100 mm rain | 0.004 |
| Rain-fed false alarms on held-out unfarmed deserts (< 100 mm rain, < 1,000 ha farmed) | 0.010 |
| Egypt, cells with < 50 mm rain: crops suitable in rain-fed / irrigated mode (deployed model) | 0.03 / 10.9 |
| Leave-Egypt-out: AUC over Egypt's crop x cell pairs (MapSPAM) | 0.853 |
| Leave-Egypt-out: FAOSTAT Egypt AUC / TSS (grown vs not grown) | 0.922 / 0.455 |
| Deployed model (fit check, Egypt in training): FAOSTAT AUC / TSS | 0.960 / 0.636 |
| v1 vs v2 on the 13 shared crops: FAOSTAT AUC | v1 0.62, v2 held-out 0.95, v2 deployed 1.00 |

**Most informative NASA measurements** (drop in held-out AUC when shuffled): T2M (temperature) 0.228, PRECTOTCORR (rain) 0.075, irrigation share (MapSPAM) 0.031, RH2M (humidity) 0.029, T2M_MAX (heat) 0.013, GWETROOT (root-zone soil wetness) 0.007, GWETTOP (surface soil wetness) 0.002.

**Intended use.** Regional screening and storytelling (about 55 km cells): comparing places, crops and directions of change. Not for parcel-level investment decisions, yield prediction or agronomic advice.

**Limitations.**
* MapSPAM is itself a model. It spreads national statistics using crop-suitability layers (GAEZ), so part of its geography is climate-informed. We learn where crops *are* grown, which also reflects markets, policy, diet and water, not only climate.
* NASA's soil wetness comes from a land model without irrigation. In irrigated mode it describes the natural land, not the watered field. Irrigated mode assumes water exists. Use `nile_farmland` to see where it does today.
* Leave-Egypt-out, water-demanding crops that Egypt grows with Nile water score low (rice, maize, sorghum, sweet potato, beans, soybean, groundnut, sunflower, sesame, sugarcane, sugar beet, banana). Outside Egypt, irrigated deserts are mostly small groundwater farms. The deployed model includes Egypt's own farmland. Grown crops still below 0.5 in the deployed model: barley, sweet potato, beans, soybean, groundnut, sunflower, sesame, banana.
* Absence in FAOSTAT is weak evidence (economics decide too). Olive and date palm are not separate MapSPAM crops and are not covered.
* Data quality: NASA POWER PRECTOTCORR over Egypt's farmland steps up by +154% from 2015 (mean 23.3 before, 59.2 after; Pettitt test p < 0.001). The step may be real or a change in the data product; we could not confirm which. A straight trend through a step overstates the long-term trend, so treat this measurement's trend and the projections that extend it with caution. NASA's soil wetness, which responds to rainfall, rises at the same time.
* Projections extend 2001 to 2025 Theil-Sen trends and are not climate forecasts. Future climates outside the training range are flagged (`in_training_range`). Mann-Kendall p-values are shown as confidence levels (strong / moderate / not proven), never as "the probability the trend is true". No serial-correlation correction.

**How a scientist could check us.** `python run.py crop-model` runs the model on the Egypt NASA data in this repo and writes the file the app shows; `python run.py check` compares Cairo with the numbers of the training run. v2's numbers are in `ml/crop_model/metrics.json`, v3's in `ml/crop_model/metrics_v3.json` and `ml/crop_model/retrain/results/`; the training table and notebook are in `ml/crop_model/training/` (steps in `ml/crop_model/README.md`). When the model came into the repo (Sat 14 Nov) our re-run equalled the training run on all 77,280 Egypt scores.

**In the app.** Scores are shown as 0 to 100. The evidence badges in the farming tabs are NOT the Mann-Kendall labels of this model: they come from our trend engine (decision D1, with FDR). Places with no farmland today and climates outside the training range are flagged in the place panel.
