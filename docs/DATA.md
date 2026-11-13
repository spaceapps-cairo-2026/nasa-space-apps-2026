# Data plan (verified Fri 13 Nov, 11:15 Cairo)

## 0. Official challenge resources (PASTE HERE)

The official Resources tab was down/blocked for automated reading. Lane C: open
https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/?tab=resources
and paste every resource name + link here. If a listed dataset covers NDVI, land temperature,
soil moisture or precipitation, prefer it over our choices below.

## 1. NASA POWER (climate, all Egypt) : VERIFIED, NO LOGIN

- What: monthly grids from NASA's MERRA-2 model (a physics model that blends many satellite and ground observations into a consistent record).
- Grid: 357 cells over the Egypt box (lat 22 to 32, lon 25 to 35), about 0.5 x 0.625 degrees (roughly 55 x 60 km per cell).
- Period: Jan 2001 to Dec 2025. Missing values: 0.75%.
- Variables: T2M (air temp), T2M_MAX (daily max air temp), PRECTOTCORR (rain), GWETTOP (topsoil wetness), GWETROOT (root zone wetness), RH2M (humidity).
- **Already in the repo:** raw downloads in `data/cache/power/`, the tidy table in `data/processed/power_monthly.parquet` (columns: cell_id, lat, lon, time, variable, value). No download needed after cloning.
- Rebuild from NASA: `python run.py power --force` (about 10 seconds).
- First look (Hamed-Rao / Yue-Wang Mann-Kendall on annual means):
  - T2M: 202 cells significantly warming, 0 cooling, median +0.24 C/decade.
  - T2M_MAX: falls in the west and south, rises in the east (Sinai, Red Sea). The number of significant cells changes a lot between test variants (65 with Hamed-Rao vs 266 with Yue-Wang). Yue-Wang turned out to be broken on short series (see METHODS.md), so trust the lower number until rechecked with FDR.
  - PRECTOTCORR: "significant" increases over hyper-arid desert. **Suspect artifact** (near-zero values, many ties). Treat precipitation over desert with a caution label.

## 1b. NASA POWER point API (any location on Earth) : VERIFIED, NO LOGIN
- `https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,GWETROOT,RH2M&community=AG&latitude=LAT&longitude=LON&start=2001&end=2025&format=JSON`
- About 1.3 s per point. Cache every point used in the demo.

## 1c. FAO ECOCROP crop requirements : SOURCE VERIFIED
- Per crop: optimal and absolute minimum/maximum temperature and annual rainfall (plus other descriptors).
- FAO data sheets: https://ecocrop.apps.fao.org/ecocrop/srv/en/ (search a crop, open its data sheet). Also packaged for 1,710 plants in the R package Recocrop (`ecocropPars`).
- Lane C: build `data/crops/crops.csv` for the crops chosen in decision D6, one row per crop, with the source link per row.

## 2. MODIS via AppEEARS (OPTIONAL, P2 evidence layer only)

AppEEARS is NASA's service that cuts satellite products down to your area and dates, and returns ready files.

| Product | Layer | What it measures | Native | Period |
|---|---|---|---|---|
| MOD13A3.061 | `_1_km_monthly_NDVI` | Vegetation greenness (0 = bare, 0.8+ = dense crops) | 1 km monthly | Feb 2000 to now |
| MOD13A3.061 | `_1_km_monthly_pixel_reliability` | Quality flag per pixel | 1 km monthly | same |
| MYD11A2.061 | `LST_Day_1km` | Land surface temperature by day, Aqua satellite (Terra drifts after 2019, so use Aqua) | 1 km 8-day | Jul 2002 to now |
| MYD11A2.061 | `QC_Day` | Quality flag | 1 km 8-day | same |

Layer names verified against the AppEEARS product API on 13 Nov.

### Areas of interest (approximate boxes; check on NASA Worldview at kickoff)

| Name | Expected story | Lat | Lon |
|---|---|---|---|
| east_owainat | desert to center-pivot farms: greening, land cooling | 22.2 to 22.9 | 28.2 to 28.9 |
| toshka | reclamation fed by Nile/Lake Nasser canal: greening | 22.4 to 23.1 | 30.9 to 31.9 |
| new_delta | new reclamation west of the Delta: greening | 30.1 to 30.9 | 29.6 to 30.6 |
| greater_cairo | urban expansion onto farmland: browning, heating | 29.85 to 30.25 | 31.05 to 31.55 |
| delta_core | old farmland with village/city growth: mixed | 30.6 to 31.3 | 30.6 to 31.6 |

### How
1. Each person: free Earthdata account at https://urs.earthdata.nasa.gov (if not done).
2. In PowerShell: `$env:EARTHDATA_USERNAME="..."; $env:EARTHDATA_PASSWORD="..."; python data/appeears_request.py submit`
3. Check: `python data/appeears_request.py status`. When "done": `python data/appeears_request.py download`.
4. Files land in data/cache/appeears/ (gitignored). Share them over Google Drive if teammates need them; do not push to GitHub.

## 3. Validation data : VERIFIED, NO LOGIN

- NASA GISTEMP v4 global annual means: https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv
  Check: our Sen's slope over 2003 to 2025 must reproduce the published rate (about +0.27 to +0.28 C/decade). Put the comparison table in the model card.

## 4. Fallbacks (if something breaks)
- AppEEARS late or failing by Sat 13:00: build everything on NASA POWER first (it is already working), add MODIS when it lands.
- Earthdata login problems: create a second account on another teammate's email.
- Wi-Fi down: everything above is cached locally after the first run.
