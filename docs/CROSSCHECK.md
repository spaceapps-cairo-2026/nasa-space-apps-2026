# Cross-check with NASA Giovanni (Check 5 on the Methods page)

Giovanni is one of the challenge's official resources. We use it to check two things:
1. **Temperature:** NASA's own tool gives the same series and the same trend as our engine on NASA POWER.
2. **Rain:** the POWER rain record jumps around 2015 (Egypt about 3 times higher). Satellite rain (GPM IMERG) tells us if that jump is real.

Needs a free NASA Earthdata login. The files are not committed (rule 6: login data); only our result `ml/outputs/crosscheck.json` is.

## Download (6 small CSV files, about 10 minutes)

Open https://giovanni.gsfc.nasa.gov/giovanni/ and log in. Ignore "Select a Study Area" and the other filters: use the keyword box.

For each file:

1. **Select Plot:** Time Series → **Time Series, Area-Averaged**.
2. **Select Date Range:** **2001-01** to **2025-12** (if Giovanni says 2025-12 is not available, use the latest month it allows).
3. **Select Region:** see the table (Cairo = type the box; Egypt = the shape button → Countries → Egypt, with the box left empty).
4. **Select Variables:** type the keyword, tick exactly one variable, the **monthly** one.
5. **Plot Data**, wait for the chart, then **Downloads → CSV**.
6. Rename the file and put it in `D:\nasa_space_apps\data\raw\giovanni\`.

| Save as | Keyword | Tick this variable | Region |
|---|---|---|---|
| `cairo_merra2_t2m.csv` | `M2TMNXSLV` | 2-meter air temperature (T2M), monthly, MERRA-2 M2TMNXSLV v5.12.4 | box `30.95,29.8,31.55,30.2` |
| `cairo_merra2_rain.csv` | `PRECTOTCORR` | Total surface precipitation, bias corrected (PRECTOTCORR), monthly, MERRA-2 M2TMNXFLX v5.12.4 | box `30.95,29.8,31.55,30.2` |
| `cairo_imerg_rain.csv` | `GPM_3IMERGM` | Precipitation (combined microwave-IR-gauge), monthly, GPM IMERG Final Run GPM_3IMERGM v07 | box `30.95,29.8,31.55,30.2` |
| `egypt_merra2_t2m.csv` | `M2TMNXSLV` | same as above | shape: Countries → Egypt |
| `egypt_merra2_rain.csv` | `PRECTOTCORR` | same as above | shape: Countries → Egypt |
| `egypt_imerg_rain.csv` | `GPM_3IMERGM` | same as above | shape: Countries → Egypt |

The box is typed West, South, East, North. If the Egypt shape is missing, use the box `24.7,22,36.87,31.59` instead.

## Run

```powershell
python run.py crosscheck   # compares, prints a table, writes ml/outputs/crosscheck.json
python ml/validate.py      # adds it to the Methods page as Check 5
```

Any subset of the files works; at least the two `imerg_rain` files answer the rain question.
