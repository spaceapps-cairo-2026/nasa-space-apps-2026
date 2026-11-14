# Submission page text (copy field by field)

Challenge: **Be An Earth System Trend Detective!** (NASA Space Apps Challenge 2026, Cairo)
Check the field names against the 2026 submission form before pasting; the order below follows the usual Space Apps form.
Every number here comes from our own outputs (`ml/outputs/`, `docs/DECISIONS.md`, `ml/model_card.md`) or a source in `docs/REFERENCES.md`. If a number in the app changes, change it here too.

---

## Project name
CropShift Earth

## Team name
TODO (team)

## 1. Project demo
- TODO link. **Rule (Space Apps guide, confirm on the 2026 page):** a video of **30 seconds or less**, or a slide deck of **up to 7 slides** (title and intro slides count). English, or English subtitles. The link must open with no password, permission or sign-up (YouTube "unlisted" or a Google Drive link set to "anyone with the link").
- No NASA logos. AI-made images or video must be marked as AI-made. No names, voices or faces of anyone under 18.

## 2. Project links
- **Final project (live app):** TODO `https://<user>-cropshift-earth.hf.space` once the Hugging Face Space is built. Test it in a private browser window before submitting.
- **GitHub repository:** `https://github.com/spaceapps-cairo-2026/nasa-space-apps-2026` . **It is PRIVATE now (checked Sat 14 Nov). Make it public before submitting**, or judges get a 404. Its README should open with the live link and the one sentence pitch.
- **Development links:** the Hugging Face Space page (build and source of the live app): TODO `https://huggingface.co/spaces/<user>/cropshift-earth` ; the API's interactive docs: `<live link>/docs` ; the crop model card: `ml/model_card.md` in the repository; the method choice evidence: `docs/DECISIONS.md` and `docs/METHODS.md`.

## 3. Project summary (problem, solution, impact, challenge fit; about 200 words)
**Problem.** Climate data is everywhere, but people cannot tell a real change from a few unusual years, and a trend alone does not tell a farmer what to plant. In the Middle East and North Africa, the most water-scarce region in the world, where about 1 in 6 Egyptian workers farms, that gap costs harvests and money.

**Solution.** CropShift Earth is a 3D globe built on 25 years of NASA POWER data (2001 to 2025). Pick temperature, heat, rain, humidity or soil wetness and any place or country to see how fast it changes, where, since when, and how strong the evidence is ("strong", "moderate" or "not proven", with "Could this be luck?" as a percentage). For 20 countries it turns those trends into farming answers: which of 40 crops fit each place today, in 2030 and in 2035 if current trends continue, irrigated or on rain alone.

**Impact.** Farmers, investors and planners see where farming potential is rising or falling, with its evidence, in time to adapt. Every number is checked against NASA's own weather stations and satellite rain record.

**Challenge fit.** It answers each question of "Be An Earth System Trend Detective!": what is changing, where, how much, whether it is significant, and the twist of opposite trends in one country (Sudan: cooling south, warming north).

## Detailed project description

### What it does
1. **Trend detective, anywhere on Earth.** Choose one of six NASA POWER measurements (air temperature, maximum temperature, rain, humidity, surface and root zone soil wetness). For a point: a 2001 to 2025 chart with its trend line, the rate per decade in real units with a 95% range, the evidence level, and the year the change started. For a country or any region: a map of every 55 km grid cell, colored where the change is proven and see-through where it is not. The whole Earth can be colored at once.
2. **What, where, how much, and is it real.** The app answers each of the challenge's questions on screen: the measurement (what), the map (where), the rate per decade (how much), and the evidence level with a false discovery correction across the whole map (is it significant).
3. **Opposite trends from one process.** The challenge notes a variable can trend one way in one region and the opposite way in another. The app finds this automatically: in Sudan, air temperature is proven to be falling in 238 places in the south while it is proven to be rising in 26 places in the north (2001 to 2025). Egypt next door: rising in 85 of 324 places, falling in none.
4. **From trends to farming.** For 20 countries (Morocco to Iran), three tabs turn the climate trends into decisions:
   - **Crops:** which of 40 crops fit a place today, in 2030 and in 2035, irrigated or rain-fed, or where one crop fits across a country.
   - **Farmland:** where farming potential is rising or falling, with the "if current trends continue" label and a 95% range on every future view.
   - **Decisions:** ranked planning signals for investors and governments, each linked to its evidence.
5. **How we know.** A Methods page shows how every number is computed and checked, and what the limits are.
6. **Guided tour.** One button plays a 60 second story with live numbers, for anyone new to the app.

### How it works
- **Data.** NASA POWER monthly grids (built on NASA's MERRA-2) at 0.5 x 0.625 degrees, fetched live for any region and cached; Egypt and the world temperature grid ship with the app so it works offline.
- **Trend and confidence (decision D1, chosen on evidence).** Theil-Sen slope on yearly means; Mann-Kendall test with its variance corrected for year to year memory (effective sample size); Benjamini-Hochberg false discovery rate on every map; Pettitt change point for "when did it start". We tested 7 methods on 20,000 simulated places with no real trend: only this one kept false alarms near 5% (3.3 to 7.5%) while still finding real trends. Popular alternatives raised false alarms up to 25% or missed most real trends.
- **Crop model.** One XGBoost model per crop, trained on where 40 crops are grown today (IFPRI MapSPAM 2020, 22,450 farmland cells on every continent), described by 10 climate features from all six NASA POWER measurements plus the irrigation share. On regions held out of training it separates places that grow a crop from places that do not with AUC 0.90; trained without Egypt, it recognizes Egypt's real crop list (FAOSTAT) with AUC 0.93. Rain-only mode needs enough rain, so deserts are never rated rain-fed farmland.
- **Projections.** Each climate feature follows its own 2001 to 2025 trend to 2030 and 2035, the crop model is re-scored on that climate, and the 95% range comes from 200 resamples of the years. Always labeled "if current trends continue". Not a forecast.
- **Stack.** Python (FastAPI, NumPy, pandas, SciPy, statsmodels), plain HTML and JavaScript with MapLibre GL JS (globe) and Plotly (charts), no build step. Runs in one Docker container.

### Supporting evidence (how we know it works)
- **Reproduces NASA's global record.** Our engine run on NASA GISTEMP finds +0.25 °C per decade for 2001 to 2025 (strong evidence, luck below 0.1%). On NASA POWER the Arctic warms fastest, +0.35 °C per decade (strong evidence): the known Arctic amplification.
- **Checked against weather stations, place by place.** Worldwide, NASA POWER and NASA's GISTEMP stations agree on the direction of change for 87% of the area, and are never proven in opposite directions. Over Egypt the stations warm +0.42 °C per decade and prove it in 30 of 32 areas; POWER is more cautious (+0.24, proven in 12). The app shows both side by side instead of hiding the difference.
- **Found and fixed a data problem.** NASA POWER's rain over Egypt jumps about 2.6 times around 2015; NASA's GPCP satellite and gauge record rises only 1.24 times. So the jump is in the dataset, not in the sky. Every rain answer carries a caution, and the crop projections remove that one-time step before measuring the trend.
- **Spot checks match known farming.** Wheat and barley in northern Saudi Arabia, sesame, sorghum and millet in Sudan's Gezira, sugarcane and rice in Iran's Khuzestan, wheat and citrus in the Maghreb.
- **Tested.** 69 automated tests (contract, API and engine), run on every push.

### Benefits and intended impact
- **Who:** farmers and agricultural investors ("what can I grow here in 10 years?"), government planners ("which farming regions need support, which gain potential?"), and students, journalists and citizens ("is my city really getting hotter?").
- **Why it matters here:**
  - The Middle East and North Africa is the most water-scarce region in the world (World Bank, 2018).
  - The Mediterranean is already about 1.5 °C warmer than pre-industrial times and is warming faster than the global average (MedECC, 2020).
  - Over Egypt, NASA's weather stations show +0.42 °C per decade since 2001, about 1.7 times the global rate of +0.25 measured the same way.
  - About 1 in 6 Egyptian workers (17.5%) works in agriculture (ILO estimate for 2025).
- **The difference it makes:** a free, open tool that tells people not just that something changed, but whether the change is real, and what it means for the crops they grow, in time to plan. Honest by design: "not proven" is never shown as "no change", projections are never shown as forecasts, and causes are never claimed.
- **Limits we state openly:** 55 km cells (regional screening, not a single farm), irrigated mode assumes water can be supplied, and the crop model learns where crops are grown today, which reflects markets and water as well as climate.

### What makes it different
Most entries for this challenge show a globe of trends. We add three things: (1) evidence you can trust, with false alarms tested and controlled and every map corrected for testing thousands of places at once; (2) every trend checked against an independent NASA record; (3) the step from "it is changing" to "this is what it means for what you can grow", for 20 countries.

## NASA data used
- NASA POWER monthly (MERRA-2 based): T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, GWETTOP, GWETROOT, 2001 to 2025, the whole world. The data behind every map, chart and crop score.
- NASA GISTEMP v4 (global means and 250 km station grid): validation of our engine and the station line shown next to air temperature answers.
- GPCP v2.3 (NASA GSFC led): independent rain check that found the 2015 step in POWER rain.
- NASA GIBS imagery (Blue Marble, VIIRS): the globe.

## Other data used
IFPRI MapSPAM 2020 (crop maps, CC BY 4.0), FAOSTAT (crop list check), FAO ECOCROP, Natural Earth (borders, cities), EOX Sentinel-2 cloudless (close-up imagery). Full list with links: References.

## Use of artificial intelligence
- Claude (Anthropic) helped write and test the code, the checks and the documentation, and drafted this text. The team reviewed and tested everything.
- Manus (AI agent) wrote the first training notebook of the crop model (v2); the model in the app (v3.1) was retrained from it in our repository with the same algorithm.
- The crop model itself is machine learning (XGBoost), trained by us on public data. No language model writes any number in the app: every sentence is built from computed values.

## 4. Project resources (datasets, sources, references, deployment tools)
Paste `docs/REFERENCES.md`: NASA data, other data, reports, statistics methods, code libraries, deployment tools and AI tools, each with a link.
