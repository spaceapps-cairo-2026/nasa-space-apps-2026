# Data guide: what each dataset is and which feature uses it

Features (F0 to F6) and tasks (A1, C3, ...) refer to `PROJECT_PLAN.md` and `TASKS.md`.
More detail on sources and how they were verified: `docs/DATA.md`.

## Status at a glance

| # | Dataset | In the repo? | Used by | Task that brings it |
|---|---|---|---|---|
| 0 | NASA POWER grid, **whole world**, 2001 to 2025 | Yearly means: **temperature (`T2M`) is in the repo**; the other 5 measurements are still downloading (started Fri evening). Monthly tiles: lead's laptop only | F1 trend maps for any country and the whole globe | C11 |
| 1 | NASA POWER monthly grid, Egypt, 2001 to 2025 | **Yes** | F2 farmland, F3 crops, F4 decisions for Egypt; testing trend methods (D1) | done |
| 2 | NASA POWER point data, any place on Earth | No: fetched live by the app; demo points get cached | F1 city and point trends, F6 tour | C1 |
| 3 | FAO ECOCROP crop requirements, 20 candidate crops | **Yes** | F3 crops (and F2 viability, F4 decisions) | done; final 8 to 12 picked in D6 (C3) |
| 4 | NASA GISTEMP global temperature, 1880 to 2025 | **Yes** | F5 Methods page: proof our numbers are right | done (C2) |
| 5 | Official challenge Resources list | **Not yet** | may add or replace datasets | Phase 0 (lane C) |
| 6 | MODIS greenness and land temperature (AppEEARS, needs Earthdata login) | No, optional | P2 evidence layer only | C10, only if time |
| 7 | More focus countries for the farming features | Climate data is covered by the world grid (row 0) | D7: F2 to F4 outside Egypt | C9, only if time |

---

## 0. NASA POWER grid for the whole world (task C11)

**Why:** trends (F1) must work as a map anywhere on Earth. Farming features (F2 to F4) stay limited to focus countries.

**Source:** the same NASA POWER service and the same 6 measurements as the Egypt grid in section 1 (see the measurement table there). Checked: over Egypt the world download equals the Egypt download exactly (107,100 values compared).

**Grid:** 361 latitudes (-90 to 90, step 0.5) x 576 longitudes (-180 to 179.375, step 0.625) = 207,936 cells. Jan 2001 to Dec 2025.

**Files**

| File | What | In git? |
|---|---|---|
| `data/processed/world/<VARIABLE>_annual.npz` | **Use this one.** Yearly mean per cell, 2001 to 2025 (a year needs at least 9 valid months) | Yes, once the download finishes |
| `data/cache/power_world/<VARIABLE>_monthly.npy` | All 300 months per cell, 250 MB per measurement | No, lead's laptop only (ask for a copy if you need monthly values) |
| `data/cache/power_world/<VARIABLE>/*.npz` | The 648 downloaded tiles per measurement | No |

**Load it in Python**
```python
import numpy as np
z = np.load("data/processed/world/T2M_annual.npz")
values = z["values"]      # shape (361, 576, 25) = [latitude, longitude, year], NaN where there is no data
lats, lons, years = z["lats"], z["lons"], z["years"]
i = int(round((30.0 + 90) / 0.5))        # row of latitude 30.0
j = int(round((31.25 + 180) / 0.625))    # column of longitude 31.25
cairo = values[i, j, :]                  # 25 yearly mean temperatures for the Cairo cell
```

**Things to know**
- **Work on whole arrays, not cell by cell.** A Python loop over 207,936 cells x 6 measurements is slow. Compute slopes and tests with array operations.
- **Soil wetness exists only on land.** Over the ocean `GWETTOP` and `GWETROOT` are empty; use that as a land mask.
- **Rain over deserts and ice is near zero:** treat "significant" rain trends there with the same caution as in Egypt.
- Cells shrink toward the poles (the grid is in degrees), so do not count cells to measure area.

**Download / progress:** `python run.py world` (about 4 seconds per tile, 648 tiles per measurement, safe to stop and rerun). `python run.py world --status` shows how far it is.

## 1. NASA POWER monthly grid for Egypt (in the repo)

**Source:** NASA POWER (power.larc.nasa.gov), which serves NASA's MERRA-2 model. MERRA-2 combines satellite and ground observations into one consistent record. Public, no login.

**Files**
- `data/processed/power_monthly.parquet`: **use this one.** A clean table built from the raw files.
- `data/cache/power/<VARIABLE>_2001_2025.json`: the raw NASA downloads, one per variable. Only `data/power_fetch.py` reads these.

**What one row means:** one grid cell, one month, one measurement.

| Column | Meaning | Example |
|---|---|---|
| `cell_id` | grid cell name, `p_<lat>_<lon>` | `p_30.0_31.2` |
| `lat`, `lon` | center of the cell in degrees | 30.0, 31.25 |
| `time` | month, `YYYY-MM` | `2010-07` |
| `variable` | which measurement (table below) | `T2M` |
| `value` | the monthly value in the variable's unit; empty if missing | 28.4 |

**Coverage:** the box from latitude 22 to 32 and longitude 25 to 35, which is 357 cells (21 x 17). Each cell is about 0.5 x 0.625 degrees, roughly 55 x 60 km. The time span is January 2001 to December 2025: 300 months, 642,600 rows. 0.75% of values are missing.

**The 6 measurements**

| Variable | What it represents | Unit | Typical range here | Why we need it |
|---|---|---|---|---|
| `T2M` | Average air temperature 2 m above the ground | C | 6 to 38 | Is it getting hotter? (F1) Crop temperature limits (F3) |
| `T2M_MAX` | Daily maximum air temperature, averaged over the month | C | 17 to 50 | Heat stress on crops and people (F2, F3) |
| `PRECTOTCORR` | Rainfall, bias corrected, average per day in that month | mm/day (x days in the month = monthly total) | 0 to 19, mostly near 0 | Rain-fed farming limits (F3 rain-fed mode, F2) |
| `GWETTOP` | Topsoil wetness, top 5 cm | 0 = completely dry, 1 = saturated | 0.02 to 1 | Surface dryness trend (F1, F2) |
| `GWETROOT` | Soil wetness in the root zone (about the top 1 m) | 0 to 1 | 0.09 to 0.97 | Water available to plant roots (F2, F3) |
| `RH2M` | Relative humidity 2 m above the ground | % | 11 to 89 | Climate comfort, crop disease risk, evaporation (F1, F2) |

**Things to know before using it**
- **The box is wider than Egypt.** It includes edges of Libya, Sudan, Saudi Arabia, and cells over the Mediterranean and the Red Sea. Clip to Egypt's border before showing "Egypt" results.
- **Sea cells have no soil wetness.** 16 cells (Red Sea and Mediterranean) have `GWETROOT` empty for all months. Drop them from farming analysis.
- **Rain over the desert is near zero.** Trends in `PRECTOTCORR` over hyper-arid desert can look "significant" just because of many tiny or equal values. Show those with a caution label (`docs/DATA.md`).
- **Climate is not irrigation.** Most Egyptian farming is irrigated from the Nile, so low rain does not mean "cannot farm". This is why F3 has the irrigation toggle.
- **Cells are about 55 km wide.** Results are regional signals, not advice about a single field.

**Load it in Python**
```python
import pandas as pd
df = pd.read_parquet("data/processed/power_monthly.parquet")
t2m = df[df.variable == "T2M"]                        # one measurement
cairo = df[df.cell_id == "p_30.0_31.2"]               # one place, all measurements
wide = df.pivot_table(index=["cell_id", "time"], columns="variable", values="value")  # one column per measurement
```

**Rebuild from NASA** (only if needed): `python run.py power --force`, about 10 seconds.

---

## 2. NASA POWER point data, any place on Earth (task C1)

- **What:** the same NASA POWER measurements for one exact latitude and longitude, plus `T2M_MIN` (daily minimum temperature). Available for anywhere on Earth, 2001 to 2025, monthly.
- **For:** F1 when a user searches a city or clicks a point outside our precomputed region, and the F6 tour.
- **How:** the app requests it live (about 1.3 s per point). Every point used in the demo is cached in `data/cache/` so the demo works without internet. The request address is in `docs/DATA.md` section 1b.

## 3. FAO ECOCROP crop requirements (in the repo)

**Source:** FAO ECOCROP, the UN Food and Agriculture Organization's database of what each plant needs to grow. The full export (2,568 plants) is from the OpenCLIM project (github.com/OpenCLIM/ecocrop). It was spot checked against FAO's own data sheets (date palm, wheat) and matched exactly. Public, no login.

**Files**
- `data/crops/crops.csv`: **use this one.** One row per crop, 20 crops.
- `data/cache/ecocrop/EcoCrop_DB.csv`: the full database, used only by `data/crops_build.py`.

**The crops:** `group` = `plan` for the 13 candidates in `PROJECT_PLAN.md` F3 (wheat, maize, rice, cotton, potato, tomato, orange, mango, date palm, olive, grape, avocado, apple). `group` = `egypt` for 7 extra major Egyptian crops (sugarcane, sugar beet, onion, faba bean, berseem clover, barley, sorghum). Decision D6 picks the final 8 to 12.

**What the columns mean**

| Column | Meaning | Unit |
|---|---|---|
| `temp_opt_min_c`, `temp_opt_max_c` | **Optimal** temperature range: the crop grows best here | C, average during the growing season |
| `temp_abs_min_c`, `temp_abs_max_c` | **Absolute** temperature range: outside it the crop fails | C |
| `rain_opt_min_mm`, `rain_opt_max_mm` | Optimal yearly rainfall | mm per year |
| `rain_abs_min_mm`, `rain_abs_max_mm` | Absolute yearly rainfall limits | mm per year |
| `killing_temp_c` | Temperature that kills the plant in early growth (empty = not recorded) | C |
| `cycle_min_days`, `cycle_max_days` | Days from planting to harvest (365 = perennial tree) | days |
| `life_span` | annual, biennial, perennial | text |
| `salinity_opt`, `salinity_abs` | Soil salt it tolerates, optimal and absolute | text, dS/m |
| `source_url` | The crop's official FAO data sheet | link |

**How it connects to the climate grid:** compare a cell's temperature (`T2M`, `T2M_MAX`) with the temperature ranges, and its rain (`PRECTOTCORR` x days, summed over the year, in mm) with the rainfall ranges. Inside the optimal range = very suitable, between optimal and absolute = marginal, outside absolute = not suitable. The exact scoring is decision D6 / task A6.

**Important for Egypt:** almost no Egyptian cell gets the rain any crop needs, because farming there is irrigated from the Nile. In **irrigated** mode the rainfall columns are ignored and only temperature (heat) limits count. This is the irrigation toggle in F3.

**Rebuild:** `python run.py crops` (from the committed file), or `python run.py crops --force` to re-download. To add a crop, add one line to `CROPS` in `data/crops_build.py`.

## 4. NASA GISTEMP global temperature (in the repo)

**Source:** NASA GISS Surface Temperature Analysis v4 (data.giss.nasa.gov/gistemp), NASA's official record of global average surface temperature over land and ocean. Public, no login.

**Files**
- `data/processed/gistemp_global_annual.csv`: **use this one.** Columns `year` (1880 to 2025) and `anomaly_c`.
- `data/cache/gistemp/GLB.Ts+dSST.csv`: the exact NASA file, with monthly and seasonal columns too.

**What `anomaly_c` means:** how much warmer (+) or colder (-) the whole planet was that year than its 1951 to 1980 average, in C. Example: 2024 = +1.28.

**What it is for:** F5 validation. When our trend engine runs on this table, it must give NASA's published warming rate. The build script already checks this with a quick Sen's slope: **+0.280 C per decade for 2003 to 2025**, matching the published value (about 0.27 to 0.28). Task C5 repeats the check with the team's real engine and puts the comparison on the Methods page.

**Rebuild:** `python run.py gistemp`, or `python run.py gistemp --force` to re-download.

## 5. Official challenge Resources list (Phase 0)

- **What:** the datasets NASA lists for this challenge on the challenge page.
- **Action:** lane C pastes the list into `docs/DATA.md` section 0. If a listed dataset covers our measurements better, we prefer it.

## 6. MODIS via AppEEARS (optional, task C10)

- **What:** satellite images at 1 km: vegetation greenness (NDVI) and land surface temperature.
- **For:** optional evidence layer (P2), only if time remains. It needs a free Earthdata login, and the files are too big for git (shared via Google Drive).

## Rules for adding data

- Small public data (under 20 MB per file) goes in git: raw files in `data/cache/<source>/`, clean tables in `data/processed/`.
- Big files, login-only data, and `data/raw/` stay out of git.
- Every new dataset gets a row in this file **and** in `docs/REFERENCES.md`.
