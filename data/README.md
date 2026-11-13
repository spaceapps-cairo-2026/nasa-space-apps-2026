# Data guide: what each dataset is and which feature uses it

Features (F0 to F6) and tasks (A1, C3, ...) refer to `PROJECT_PLAN.md` and `TASKS.md`.
More detail on sources and how they were verified: `docs/DATA.md`.

## Status at a glance

| # | Dataset | In the repo? | Used by | Task that brings it |
|---|---|---|---|---|
| 1 | NASA POWER monthly grid, Egypt, 2001 to 2025 | **Yes** | F1 region map, F2 farmland, F3 crops, F4 decisions | done |
| 2 | NASA POWER point data, any place on Earth | No: fetched live by the app; demo points get cached | F1 city and point trends, F6 tour | C1 |
| 3 | FAO ECOCROP crop requirements | **Not yet** | F3 crops (and F2 viability, F4 decisions) | C3 (after decision D6) |
| 4 | NASA GISTEMP global temperature | **Not yet** | F5 Methods page: proof our numbers are right | C2 |
| 5 | Official challenge Resources list | **Not yet** | may add or replace datasets | Phase 0 (lane C) |
| 6 | MODIS greenness and land temperature (AppEEARS, needs Earthdata login) | No, optional | P2 evidence layer only | C10, only if time |
| 7 | NASA POWER grids for 1 or 2 more countries | No, optional | D7, regional maps outside Egypt | C9, only if time |

---

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

## 3. FAO ECOCROP crop requirements (task C3)

- **What:** for each crop, the temperature and yearly rainfall it needs: the **optimal** range (grows best) and the **absolute** range (survives at all). Published by the UN Food and Agriculture Organization.
- **For:** F3 (which crops fit a place now and in 5 or 10 years). It also feeds F2 viability and the F4 rankings.
- **Will live in:** `data/crops/crops.csv`, one row per crop (8 to 12 crops chosen in decision D6), with the FAO source link on every row.

## 4. NASA GISTEMP global temperature (task C2)

- **What:** NASA's official global average temperature per year.
- **For:** F5 validation. Our trend engine must reproduce NASA's published warming rate (about +0.27 to +0.28 C per decade, 2003 to 2025). This proves to judges that our numbers are trustworthy.
- **Source:** a public CSV, no login (address in `docs/DATA.md` section 3).

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
