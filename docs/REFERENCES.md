# References (paste into the submission page References field)

Add every item the moment you use it. Everything below is used by the app, the analysis code, the checks, or the story.

## NASA data
- NASA POWER (Prediction Of Worldwide Energy Resources), monthly regional grids and point data, 2001 to 2025, built on NASA GMAO MERRA-2; measurements T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, GWETTOP, GWETROOT. NASA Langley Research Center: https://power.larc.nasa.gov
- NASA GISS Surface Temperature Analysis (GISTEMP v4): global annual means and the 250 km gridded station anomalies (GHCN v4 stations). GISTEMP Team, 2026, NASA Goddard Institute for Space Studies: https://data.giss.nasa.gov/gistemp/ . Lenssen, N., et al., 2019: Improvements in the GISTEMP uncertainty model. J. Geophys. Res. Atmos., 124, 6307 to 6326.
- GPCP v2.3 monthly precipitation (Global Precipitation Climatology Project, satellites and rain gauges, NASA GSFC led), data from NOAA PSL: https://psl.noaa.gov/data/gridded/data.gpcp.html . Adler, R. F., et al., 2018: The Global Precipitation Climatology Project (GPCP) monthly analysis (new version 2.3) and a review of 2017 global precipitation. Atmosphere, 9, 138.
- NASA GIBS (Global Imagery Browse Services): Blue Marble shaded relief and VIIRS SNPP corrected reflectance imagery on the globe: https://earthdata.nasa.gov/gibs
- NASA Giovanni (MERRA-2 and GPM IMERG files, optional cross-check, `docs/CROSSCHECK.md`): https://giovanni.gsfc.nasa.gov

## Other data
- IFPRI MapSPAM 2020 crop maps (training the crop model): International Food Policy Research Institute (IFPRI), 2026, Global Spatially-Disaggregated Crop Production Statistics Data for 2020 Version 2.0 Release 2 (SPAM 2020 v2r2), Harvard Dataverse, https://doi.org/10.7910/DVN/SWPENT , CC BY 4.0. This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no responsibility for the analyses or interpretations of the data presented here.
- FAOSTAT crops and livestock production, Food and Agriculture Organization of the United Nations (checking the crop model against the crops Egypt grows): https://www.fao.org/faostat/
- FAO ECOCROP crop requirements database (first crop calculator, `ml/farming.py`): https://ecocrop.apps.fao.org/ecocrop/srv/en/home ; export used to build our table, OpenCLIM project: https://github.com/OpenCLIM/ecocrop
- Kaggle (training environment for crop model v2): the team's dataset `mohossameldeen/nasa-2026-earth-trends-dataset` (NASA POWER features per cell) and, for the FAOSTAT check, `sayedkhaled2000/egypt-crop-yield-processed-pivot-table`: https://www.kaggle.com
- Natural Earth (public domain): country borders (1:50m and 1:110m) and populated places for the offline search: https://www.naturalearthdata.com . Edited by us (`scripts/palestine_borders.js`): the map names Palestine and places the Golan Heights in Syria.
- Sentinel-2 cloudless 2020 by EOX IT Services (close-up imagery), contains modified Copernicus Sentinel data 2020: https://s2maps.eu
- Our World in Data, share of employment in agriculture (ILO modelled estimates, as published by the World Bank, indicator SL.AGR.EMPL.ZS), used for the impact numbers: https://ourworldindata.org/grapher/share-of-the-labor-force-employed-in-agriculture

## Reports cited in the story
- World Bank, 2018: Beyond Scarcity: Water Security in the Middle East and North Africa. MENA Development Report. https://openknowledge.worldbank.org/handle/10986/27659 (CC BY 3.0 IGO)
- MedECC, 2020: Climate and Environmental Change in the Mediterranean Basin, Current Situation and Risks for the Future. First Mediterranean Assessment Report (MAR1). https://www.medecc.org

## Statistics methods
- Mann, H. B., 1945, Nonparametric tests against trend, Econometrica 13; Kendall, M. G., 1975, Rank Correlation Methods.
- Sen, P. K., 1968, Estimates of the regression coefficient based on Kendall's tau, J. Am. Stat. Assoc. 63 (Theil-Sen slope).
- Variance correction for autocorrelation (effective sample size): Hamed, K. H. and Rao, A. R., 1998, J. Hydrology 204; Yue, S. and Wang, C. Y., 2004, Water Resources Management 18. Compared on our data in `ml/compare_methods.py`.
- Benjamini, Y. and Hochberg, Y., 1995, Controlling the false discovery rate, J. R. Stat. Soc. B 57.
- Pettitt, A. N., 1979, A non-parametric approach to the change-point problem, Applied Statistics 28.
- Chen, T. and Guestrin, C., 2016, XGBoost: A scalable tree boosting system, KDD.

## Code libraries
- Python: FastAPI, Uvicorn, NumPy, pandas, PyArrow, SciPy, statsmodels, pymannkendall, ruptures, scikit-learn, XGBoost (training only), joblib, xarray, netCDF4, python-dotenv, httpx, jsonschema, pytest
- Browser: MapLibre GL JS 5.6 (globe), Plotly.js 2.35 (charts), polygon-clipping (border cutting), Leaflet 1.9 (bundled)

## Tools used to build and deploy
- Hosting: Render (free web service, public https link): https://render.com ; the crop model is published on the Hugging Face Hub: https://huggingface.co/OmarGhost2005/cropshift-earth-crop-model
- Docker, official `python:3.12-slim` image (`deploy/Dockerfile`): https://hub.docker.com/_/python
- Git and Git LFS (pushing the app and its data files to the Space): https://git-lfs.com
- GitHub (code, pull requests) and GitHub Actions (tests on every push, `.github/workflows/check.yml`): https://github.com
- Kaggle Notebooks (training crop model v2): https://www.kaggle.com
- Python 3.12 / 3.13, Visual Studio Code, Windows PowerShell

## Images, media
- All imagery in the app comes from NASA GIBS and EOX Sentinel-2 cloudless (above). Video and slide images: list here as they are added.

## AI tools
- Claude (Anthropic): code assistance, analysis code, checks, documentation and submission text drafting, research summaries. All outputs reviewed and tested by the team.
- Manus (AI agent): training code and analysis of the crop suitability model v2 (Kaggle style notebook, `ml/crop_model/training/`). The model in the app (v3.1) was retrained from it in this repository.
