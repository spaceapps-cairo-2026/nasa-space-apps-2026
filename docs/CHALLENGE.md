# Egypt Trend Detective: same water, opposite trends

Challenge: **Be An Earth System Trend Detective!** (Advanced, Earth Science + Software)
Official page: https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/

## The official statement (key sentences)

- Change is always occurring in Earth's interconnected system; when it runs in a consistent direction, measured variables reflect it.
- **"A variable can trend one way in one region and the opposite way in another, even when the same process drives both."**
- Your challenge is to create a tool that can **select variables** measured by NASA Earth science missions or produced by NASA models, **visualize how they change over time**, and determine:
  1. **what** is changing,
  2. **where** it is changing,
  3. **how much** it is changing,
  4. whether the changes are **"significant"** in the scientific sense.

The Resources tab (released 13 Nov) could not be read automatically. **Lane C: paste its full list into `docs/DATA.md` section 0 tonight**, and prefer any dataset listed there (judges reward "Best Use of Data" for the challenge's own resources).

## Requirement to feature map (every row must be a visible feature in the demo)

| Requirement | Our feature | Lane |
|---|---|---|
| Select variables (NASA missions or models) | Variable picker: MODIS NDVI, MODIS Aqua land surface temperature, MERRA-2 air temp / max temp / soil wetness / precipitation (via NASA POWER) | B |
| Visualize change over time | Map colored by trend + click any place for its time series with the trend line and the change point | B |
| What is changing | Variable + direction label ("greening", "warming", "drying") | A |
| Where | Map of significant cells only; "opposite trend" regions highlighted | A + B |
| How much | Sen's slope in real units per decade (e.g. "+0.04 NDVI/decade", "-0.6 C/decade") | A |
| Significant? | Autocorrelation-corrected Mann-Kendall p-value + false discovery rate q-value; "not significant" shown as "not proven", never "no change" | A |
| Opposite trends, same process | **Trend fingerprints (AI):** unsupervised clustering of multi-variable trends discovers "new farmland" (greening + land cooling) vs "urban sprawl on farmland" (browning + land heating) | A |

## Our story (the 20 second pitch)

Egypt is warming almost everywhere: in our first check, 202 of 357 NASA grid cells show significant air temperature rise. But where Egypt **adds Nile water to the desert** (Toshka, East Owainat, the New Delta), the land surface turns **greener and cooler**, while where **cities grow over old Delta farmland**, it turns **browner and hotter**. Same driver (how Egypt moves its water and land), **opposite trends**. Our tool finds these places automatically, measures how fast, proves which changes are statistically real, and dates when each one started.

## User

- Primary: an analyst at Egypt's agriculture or water ministry, or a regional planner, who must decide where reclamation is working and where farmland is being lost.
- Secondary: a university student or teacher who wants to learn what "significant" means with real data.

## Output (what the model produces)

For every grid cell or 1 km pixel, and every variable:
direction, Sen's slope per decade, p, q, significant yes/no, change point year, fingerprint cluster, and a plain language sentence.

## Data (see docs/DATA.md for verified access)

1. NASA POWER monthly (MERRA-2 based), all Egypt, 0.5 deg, 2001 to 2025. Verified, no login, 9 seconds.
2. MODIS MOD13A3 NDVI monthly 1 km, and MODIS Aqua MYD11A2 land surface temperature 1 km, via AppEEARS for 5 areas of interest. Requires Earthdata login. **Submit tonight**, processing takes hours.
3. Validation: NASA GISTEMP v4 global means (public CSV) to prove our trend engine reproduces a published number.

## Scope cuts (decided now, not negotiable at 3 AM)

- Egypt only. No global globe (dozens of teams built one already).
- Monthly and annual data only. No daily data.
- No forecasting into the future. Trends describe the past; we say so.
- No causal claims. We show co-located opposite trends and known land-use history; we say "consistent with", never "caused by".
- The AI narrative, if built, only restates computed numbers.
