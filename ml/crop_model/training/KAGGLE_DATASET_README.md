# CropShift v2 training cells: where 46 crops grow, matched to six NASA POWER measurements

One row per NASA POWER grid cell (0.5° latitude × 0.625° longitude) that has farmland in IFPRI's MapSPAM 2020 crop map. Each row combines:

- **the 2001 to 2025 climate of the cell**, given as 10 features computed from the six NASA POWER monthly measurements used in the NASA Space Apps 2026 "Earth System Trend Detective" project;
- **the harvested area of 46 crops in the cell** (MapSPAM 2020, about 2019 to 2021), split into all, irrigated and rain-fed farming.

It is the training table of the CropShift Earth crop-suitability model (NASA Space Apps 2026 Cairo). It is built so that the same features can be computed from our Egypt NASA POWER dataset (`mohossameldeen/nasa-2026-earth-trends-dataset`) and from live NASA POWER requests.

## File

`cropshift_v2_training_cells.parquet`: 31,333 rows, 157 columns, 7.4 MB. 177 countries, latitudes 53°S to 70°N.

| Column | Meaning |
|---|---|
| `ilat`, `ilon` | row and column index on the NASA POWER grid (lat = -90 + 0.5·ilat, lon = -180 + 0.625·ilon) |
| `lat`, `lon` | cell centre (degrees) |
| `country` | MapSPAM country with the largest harvested area in the cell |
| `cell_area_ha` | area of the grid cell on the sphere (ha) |
| `t_mean`, `t_coldest`, `t_warmest` | T2M: annual mean, coldest-month and warmest-month temperature (°C) |
| `tmax_hottest` | T2M_MAX: highest monthly maximum temperature (°C) |
| `rain_annual` | PRECTOTCORR: annual rainfall (mm) |
| `rain_wettest3_share` | PRECTOTCORR: share of annual rain falling in the wettest 3 consecutive months |
| `rh_mean` | RH2M: annual mean relative humidity at 2 m (%) |
| `soil_top_wetness` | GWETTOP: annual mean surface soil wetness (0 to 1) |
| `soil_root_wetness`, `soil_root_wetness_min` | GWETROOT: annual mean and driest-month root-zone soil wetness (0 to 1) |
| `TA_<crop>` | MapSPAM 2020 harvested area, all farming (ha) |
| `TI_<crop>` | harvested area, irrigated (ha) |
| `TR_<crop>` | harvested area, rain-fed (ha) |
| `TA_total`, `TI_total`, `TR_total` | sums over all 46 crops |

Climate features are the mean of the 25 annual values for 2001 to 2025. Monthly rainfall uses mm/day × days in month (February = 28.25).

Crop codes are MapSPAM codes: whea wheat, rice, maiz maize, barl barley, pmil pearl millet, mill small millets, sorg sorghum, ocer other cereals, pota potato, swpo sweet potato, yams, cass cassava, orts other roots, bean beans, chic chickpea, cowp cowpea, pige pigeon pea, lent lentil, opul other pulses, soyb soybean, grou groundnut, cnut coconut, oilp oil palm, sunf sunflower, rape rapeseed, sesa sesame, ooil other oil crops, sugc sugarcane, sugb sugar beet, cott cotton, ofib other fibre crops, coff arabica coffee, rcof robusta coffee, coco cocoa, teas tea, toba tobacco, bana banana, plnt plantain, citr citrus, trof tropical fruit, temf temperate fruit, toma tomato, onio onion, vege vegetables, rest rest of crops, rubb rubber.

## How it was built

1. **MapSPAM 2020 v2r2** global harvested area (5 arc-minute grid, about 10 km) was summed onto the NASA POWER grid for each crop and each farming system.
2. The six NASA POWER variables (T2M, T2M_MAX, PRECTOTCORR, RH2M, GWETTOP, GWETROOT) were read for 2001 to 2025, monthly, 60°S to 75°N, from the official NASA POWER archive on AWS (`power_merra2_monthly_temporal_utc.zarr`).
3. Ten features were computed for each year, then averaged over 2001 to 2025. Cells missing any feature were dropped.

On the Egypt grid, these features match features computed from `mohossameldeen/nasa-2026-earth-trends-dataset` within 0.01 °C and 0.1 mm/year. The CropShift v2 notebook can rebuild this table from the original sources when Internet is on.

## Suggested use

In the CropShift model, a cell is **farmland** if `TA_total >= 1000` ha (22,450 cells). A crop is **grown** in a cell if it covers at least 2% of the cell's harvested area, and **not grown** if it covers at most 0.2%. The irrigation share is `TI_total / TA_total`. Validate with spatial blocks (for example 10° × 10°), because neighbouring cells are strongly correlated.

## Caveats

MapSPAM is a modelled allocation of national and sub-national statistics to the grid, not a field survey. Its allocation partly uses crop-suitability information, so models trained on it partly learn that information back. Harvested area reflects markets, water access and policy as well as climate. "Not grown here" therefore does not mean "cannot be grown here". Climate features are 2001 to 2025 averages; MapSPAM describes about 2019 to 2021.

Over Egypt, NASA POWER `PRECTOTCORR` steps up from 2015: the farmland mean is about 23 mm/year in 2001 to 2014 and about 59 mm/year in 2015 to 2025 (Pettitt test p < 0.001). We have not identified the cause; it may be real or a change in the data product. The 25-year averages in this table are affected much less than a trend line would be, but rainfall in very dry cells should be read with this in mind.

## Sources and licence

- International Food Policy Research Institute (IFPRI), 2026. *Global Spatially-Disaggregated Crop Production Statistics Data for 2020 Version 2.0 Release 2* (SPAM 2020 v2r2). Harvard Dataverse, V5. https://doi.org/10.7910/DVN/SWPENT. Licence: CC BY 4.0.
- Yu, Q. et al., 2020. A cultivated planet in 2010, Part 2: the global gridded agricultural-production maps. *Earth System Science Data* 12, 3545 to 3572 (SPAM method).
- NASA Langley Research Center POWER Project, funded through the NASA Earth Science/Applied Science Program. https://power.larc.nasa.gov/ (data on the AWS Registry of Open Data).

This derived table is shared under **CC BY 4.0**.

*This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no responsibility for the analyses or interpretations of the data presented here.*
