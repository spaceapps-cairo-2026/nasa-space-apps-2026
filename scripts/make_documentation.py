"""Build the project documentation PDF (Cairo local submission form): docs/documentation/CropShift_Earth_Documentation.pdf

    python scripts/make_documentation.py            numbers and figures from the live app (Render)
    python scripts/make_documentation.py --local    from a local server at http://localhost:8000

No LaTeX on the team laptops, so the paper layout is HTML + CSS printed to PDF by Chrome (headless).
Every number in the figures is read from the API at build time; the text numbers match docs/SUBMISSION.md.
"""
from __future__ import annotations

import base64
import html
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "documentation"
API = "http://localhost:8000" if "--local" in sys.argv else "https://cropshift-earth.onrender.com"
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]

LINKS = [
    ("NASA Space Apps project page", "https://www.spaceappschallenge.org/2026/find-a-team/tech-ghosts/"),
    ("Live app", "https://cropshift-earth.onrender.com"),
    ("Source code", "https://github.com/spaceapps-cairo-2026/nasa-space-apps-2026"),
    ("Trained crop model and model card", "https://huggingface.co/OmarGhost2005/cropshift-earth-crop-model"),
    ("API documentation", "https://cropshift-earth.onrender.com/docs"),
]


def get(path: str) -> dict:
    with urllib.request.urlopen(API + path, timeout=180) as r:
        return json.load(r)


def region(iso: str, boxes: dict) -> dict:
    w, s, e, n = boxes[iso]
    return get(f"/api/trend/region?lat_min={s}&lat_max={n}&lon_min={w}&lon_max={e}&variable=T2M&country={iso}")


# ---------- figures (inline SVG) ----------

def _color(slope: float, vmax: float) -> str:
    """Blue (cooling) to red (warming), white at zero."""
    t = max(-1.0, min(1.0, slope / vmax))
    if t >= 0:
        r, g, b = 255, int(255 - 185 * t), int(255 - 205 * t)
    else:
        r, g, b = int(255 + 205 * t), int(255 + 140 * t), 255
    return f"rgb({r},{g},{b})"


def map_svg(d: dict, title: str, width: int = 330) -> str:
    g = d["grid"]
    lats, lons = g["lats"], g["lons"]
    dlat, dlon = g["lat_step"], g["lon_step"]
    span_lon = (lons[-1] - lons[0]) + dlon
    span_lat = (lats[-1] - lats[0]) + dlat
    sx = width / span_lon
    sy = sx * 1.0
    height = span_lat * sy
    vmax = 0.6
    cells = []
    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            lev = g["level"][i][j]
            if lev is None or lev < 0:
                continue
            slope = g["slope_per_decade"][i][j]
            x = (lon - lons[0]) * sx
            y = (lats[-1] - lat) * sy
            if lev >= 1 and slope is not None:
                fill, op = _color(slope, vmax), 1.0
            else:
                fill, op = "#d9d9d9", 0.8
            cells.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{sx * dlon + .3:.1f}" height="{sy * dlat + .3:.1f}" '
                         f'fill="{fill}" fill-opacity="{op}"/>')
    return (f'<svg viewBox="-2 -2 {width + 4:.0f} {height + 4:.0f}" width="{width}" height="{height:.0f}" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{html.escape(title)}">{"".join(cells)}</svg>')


def legend_svg() -> str:
    stops = [-0.6, -0.4, -0.2, 0, 0.2, 0.4, 0.6]
    boxes = "".join(f'<rect x="{20 + k * 38}" y="4" width="38" height="12" fill="{_color(v, 0.6)}" stroke="#999" stroke-width=".3"/>'
                    f'<text x="{39 + k * 38}" y="28" font-size="9" text-anchor="middle">{v:+.1f}</text>'
                    for k, v in enumerate(stops))
    return (f'<svg viewBox="0 0 420 48" width="420" height="48" xmlns="http://www.w3.org/2000/svg">{boxes}'
            f'<rect x="310" y="4" width="20" height="12" fill="#d9d9d9"/>'
            f'<text x="336" y="14" font-size="9">not proven</text>'
            f'<text x="20" y="45" font-size="8.5" fill="#444">proven change, °C per decade (blue cooling, red warming)</text></svg>')


def series_svg(point: dict, width: int = 560, height: int = 230) -> str:
    s = point["series"]
    years = [p["t"] for p in s]
    vals = [p["v"] for p in s]
    tl = point["trend_line"]
    lo, hi = min(vals) - 0.2, max(vals) + 0.2
    pad_l, pad_b, pad_t, pad_r = 44, 28, 10, 10
    W, H = width - pad_l - pad_r, height - pad_b - pad_t

    def X(t): return pad_l + (t - years[0]) / (years[-1] - years[0]) * W
    def Y(v): return pad_t + (hi - v) / (hi - lo) * H

    pts = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in zip(years, vals))
    dots = "".join(f'<circle cx="{X(t):.1f}" cy="{Y(v):.1f}" r="2.4" fill="#1f4e79"/>' for t, v in zip(years, vals))
    trend = (f'<line x1="{X(tl[0]["t"]):.1f}" y1="{Y(tl[0]["v"]):.1f}" x2="{X(tl[-1]["t"]):.1f}" y2="{Y(tl[-1]["v"]):.1f}" '
             f'stroke="#c0392b" stroke-width="2"/>')
    yt = ""
    step = 0.5
    v = round(lo / step) * step
    while v <= hi:
        if v >= lo:
            yt += (f'<line x1="{pad_l}" x2="{pad_l + W}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#e5e5e5"/>'
                   f'<text x="{pad_l - 6}" y="{Y(v) + 3:.1f}" font-size="9" text-anchor="end">{v:.1f}</text>')
        v += step
    xt = "".join(f'<text x="{X(t):.1f}" y="{pad_t + H + 16}" font-size="9" text-anchor="middle">{t}</text>'
                 for t in years if t % 4 == 1)
    return (f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
            f'{yt}<polyline points="{pts}" fill="none" stroke="#1f4e79" stroke-width="1" opacity=".5"/>{dots}{trend}{xt}'
            f'<text x="12" y="{pad_t + H / 2}" font-size="9" transform="rotate(-90 12 {pad_t + H / 2})" text-anchor="middle">°C, yearly mean</text>'
            f'</svg>')


def bars_svg(rows: list[tuple[str, float, str]], width: int = 560) -> str:
    vmax = max(v for _, v, _ in rows) * 1.6
    h = 26 * len(rows) + 10
    out = []
    for k, (label, v, color) in enumerate(rows):
        y = 6 + k * 26
        w = (width - 250) * v / vmax
        out.append(f'<text x="0" y="{y + 13}" font-size="10">{html.escape(label)}</text>'
                   f'<rect x="240" y="{y + 2}" width="{w:.1f}" height="15" fill="{color}"/>'
                   f'<text x="{245 + w:.1f}" y="{y + 14}" font-size="10">+{v:.2f} °C / decade</text>')
    return f'<svg viewBox="0 0 {width} {h}" width="{width}" height="{h}" xmlns="http://www.w3.org/2000/svg">{"".join(out)}</svg>'


# ---------- document ----------

CSS = """
@page { size: A4; margin: 20mm 20mm 20mm 20mm; }
body { font-family: Cambria, "Times New Roman", Georgia, serif; font-size: 10.6pt; line-height: 1.42; color: #111; }
h1 { font-size: 24pt; margin: 0 0 4pt; font-weight: 700; letter-spacing: .2pt; }
h2 { font-size: 13.5pt; margin: 18pt 0 6pt; border-bottom: .6pt solid #999; padding-bottom: 2pt; break-after: avoid; }
h3 { font-size: 11pt; margin: 10pt 0 3pt; break-after: avoid; }
p { margin: 0 0 6pt; text-align: justify; hyphens: auto; }
ul { margin: 2pt 0 6pt 16pt; padding: 0; } li { margin: 0 0 2pt; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; font-size: 9.6pt; break-inside: avoid; }
th, td { border-top: .5pt solid #bbb; border-bottom: .5pt solid #bbb; padding: 3pt 5pt; text-align: left; vertical-align: top; }
th { background: #f1f3f6; }
.title { text-align: center; margin: 30pt 0 18pt; }
.subtitle { font-size: 12.5pt; color: #333; margin: 2pt 0; }
.meta { font-size: 10pt; color: #444; margin-top: 8pt; }
.abstract { margin: 10pt 24pt 14pt; font-size: 10.2pt; }
.abstract b.h { display: block; text-align: center; margin-bottom: 4pt; }
figure { margin: 8pt 0 10pt; text-align: center; break-inside: avoid; }
figcaption { font-size: 9.2pt; color: #333; margin-top: 4pt; text-align: left; }
.maps { display: flex; justify-content: space-around; align-items: flex-end; gap: 10pt; }
.maps div { font-size: 9.2pt; }
img.shot { width: 100%; border: .5pt solid #888; }
.small { font-size: 9.2pt; color: #333; }
a { color: #1f4e79; text-decoration: none; word-break: break-all; }
.ok { color: #1e7b34; font-weight: 700; } .no { color: #8a5a00; font-weight: 700; }
.pb { break-before: page; }
"""


def build() -> str:
    boxes = {c["iso"]: c["bbox"] for c in get("/api/farming/countries")["countries"]}
    egy, sdn = region("EGY", boxes), region("SDN", boxes)
    cairo = get("/api/trend/point?lat=30.04&lon=31.24&variable=T2M")
    val = get("/api/validation")
    shot = OUT_DIR / "app_welcome.png"
    shot_tag = (f'<img class="shot" src="data:image/png;base64,{base64.b64encode(shot.read_bytes()).decode()}" '
                f'alt="CropShift Earth start screen">') if shot.exists() else ""
    es, ss = egy["summary"], sdn["summary"]
    ct, st = cairo["trend"], cairo.get("station_check") or {}
    xc = val["checks"]["cross_check"]

    links_rows = "".join(f"<tr><td>{html.escape(n)}</td><td><a href='{u}'>{u}</a></td></tr>" for n, u in LINKS)
    links_rows += "<tr><td>Demo video (30 s)</td><td>linked on the NASA Space Apps project page</td></tr>"

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>CropShift Earth: project documentation</title>
<style>{CSS}</style></head><body>

<div class="title">
  <h1>CropShift Earth</h1>
  <div class="subtitle">Is our planet really changing, and what can we still grow?</div>
  <div class="meta">NASA Space Apps Challenge 2026, Cairo &middot; Challenge: <b>Be An Earth System Trend Detective!</b><br>
  Team <b>Tech Ghosts</b> &middot; 14 to 15 November 2026</div>
</div>

<table><tr><th style="width:34%">Link</th><th>Address</th></tr>{links_rows}</table>

<div class="abstract"><b class="h">Summary</b>
<p><b>Problem.</b> Climate data is everywhere, but people cannot tell a real change from a few unusual years, and a trend alone does not tell a farmer what to plant. The Middle East and North Africa is the most water-scarce region in the world, and about 1 in 6 Egyptian workers farms.</p>
<p><b>Solution.</b> CropShift Earth is a 3D globe built on 25 years of NASA POWER data (2001 to 2025). Pick a measurement and any place or country to see how fast it changes, where, since when, and how strong the evidence is (&ldquo;strong&rdquo;, &ldquo;moderate&rdquo; or &ldquo;not proven&rdquo;). For 20 countries it turns those trends into farming answers: which of 40 crops fit each place today, in 2030 and in 2035 if current trends continue, irrigated or rain-fed.</p>
<p><b>Impact.</b> Farmers, investors and planners see where farming potential is rising or falling, with its evidence, in time to adapt. Every number is checked against NASA&rsquo;s own weather stations and satellite rain record.</p>
<p><b>Challenge fit.</b> It answers each question of the challenge: what is changing, where, how much, whether it is significant, and the twist of opposite trends in one country (Sudan: cooling south, warming north).</p>
</div>

<h2>1. The challenge and how we answer it</h2>
<table>
<tr><th style="width:42%">The challenge asks</th><th>Where it is in CropShift Earth</th></tr>
<tr><td>Select variables measured by NASA missions or models</td><td>Six NASA POWER measurements: air temperature, maximum temperature, rain, humidity, surface and root zone soil wetness</td></tr>
<tr><td>Visualize how they change over time</td><td>25 year chart with its trend line for any point (Figure 3)</td></tr>
<tr><td>What is changing</td><td>The measurement and the direction (rising, falling, not proven)</td></tr>
<tr><td>Where it is changing</td><td>Trend map of every 55 km grid cell of any country or region, and the whole Earth at once (Figures 1 and 2)</td></tr>
<tr><td>How much it is changing</td><td>Rate per decade in real units with its 95% range, and the total change since 2001</td></tr>
<tr><td>Whether the change is significant</td><td>Evidence level and &ldquo;Could this be luck?&rdquo; as a percentage; false discovery correction across each map</td></tr>
<tr><td>Opposite trends from one process in different regions</td><td>Found automatically: in Sudan, {ss['decreasing']} places proven cooling in the south, {ss['increasing']} proven warming in the north (Figure 2)</td></tr>
</table>

<h2>2. What it does</h2>
<figure>{shot_tag}<figcaption><b>App screen.</b> The start screen of the live app, with the trend panel on the left. Behind the welcome box the globe is colored where change is proven (the globe is not drawn in this automatic screenshot).</figcaption></figure>
<h3>Working features</h3>
<ul>
<li><span class="ok">Working</span> <b>Trend explorer, anywhere on Earth.</b> Click a place or search a country or one of about 1,250 cities. For a point: chart, trend line, rate per decade, 95% range, evidence level, the year the change started, and for air temperature the same trend from NASA&rsquo;s weather stations next to it. For a country or region: a map of every grid cell; proven cells are colored, the others are see-through.</li>
<li><span class="ok">Working</span> <b>Whole Earth layer.</b> Air temperature for every land and sea cell at once: 2001 to 2025, about 29,600 cells proven rising and 900 proven falling of about 208,000.</li>
<li><span class="ok">Working</span> <b>Custom years.</b> Any range of at least 10 years between 2001 and 2025.</li>
<li><span class="ok">Working</span> <b>Crops tab</b> (20 countries of the Middle East and North Africa): which of 40 crops fit a place today, in 2030 and in 2035, irrigated or rain-fed, or where one crop fits across a country.</li>
<li><span class="ok">Working</span> <b>Farmland tab:</b> where farming potential is rising or falling, with the label &ldquo;if current trends continue&rdquo; and a 95% range.</li>
<li><span class="ok">Working</span> <b>Decisions tab:</b> ranked planning signals for investors and governments, each with its evidence.</li>
<li><span class="ok">Working</span> <b>How we know:</b> a Methods page with every check, and a 60 second guided tour.</li>
</ul>

<h2>3. How it works</h2>
<h3>Data</h3>
<p>NASA POWER monthly grids (built on NASA&rsquo;s MERRA-2 reanalysis) at 0.5 x 0.625 degrees, 2001 to 2025, for six measurements. Any region is fetched live from NASA the first time and kept on disk; Egypt and the world air temperature grid ship with the app, so the demo works even if NASA is slow.</p>
<h3>Is the change real? (trend and confidence)</h3>
<p>For each place we take yearly means and measure the rate with the Theil-Sen slope. Confidence comes from the Mann-Kendall test with its variance corrected for year to year memory (effective sample size). On every map, the Benjamini-Hochberg false discovery rate correction accounts for testing hundreds of places at once. The Pettitt test finds the year a change started. We chose this method on evidence: 7 methods were run on 20,000 simulated places with no real trend, and only this one kept false alarms near 5% (3.3 to 7.5%) while still finding real trends. Popular alternatives raised false alarms up to 25% or missed most real trends.</p>
<p>Evidence levels: <b>strong</b> (below 1%), <b>moderate</b> (below 5%), <b>not proven</b> (the rest). The exact number is always shown as &ldquo;Could this be luck?&rdquo;: how often a trend this strong would appear if nothing were really changing. &ldquo;Not proven&rdquo; is never shown as &ldquo;no change&rdquo;.</p>
<h3>What can we still grow? (crop model)</h3>
<p>One XGBoost model per crop, trained on where 40 crops are grown today (IFPRI MapSPAM 2020, 22,450 farmland cells on every continent), each place described by 10 climate features from all six NASA POWER measurements plus the share of irrigation. On regions held out of training the model tells places that grow a crop from places that do not with AUC 0.90; trained without Egypt, it recognizes Egypt&rsquo;s real crop list (FAOSTAT) with AUC 0.93. In rain-only mode a rain gate keeps deserts from being rated as rain-fed farmland. The 8,000 trees are packed so the model runs with numpy only (published on Hugging Face).</p>
<h3>Projections</h3>
<p>Each climate feature follows its own 2001 to 2025 trend to 2030 and 2035, the crop model is scored again on that climate, and the 95% range comes from 200 block resamples of the years. Every future view says &ldquo;if current trends continue&rdquo;. It is not a climate forecast.</p>
<h3>System</h3>
<p>NASA POWER (live and cached) &rarr; trend engine and crop outlook (Python) &rarr; FastAPI server with documented endpoints &rarr; browser app (MapLibre GL JS globe, Plotly charts, plain JavaScript). One server process; hosted on Render. 69 automated tests run on every push.</p>

<h2 class="pb">4. Results and supporting evidence</h2>
<figure><div class="maps">
<div>{map_svg(egy, "Egypt air temperature trend map", 300)}<br>Egypt: {es['increasing']} of {es['cells']} places proven warming</div>
<div>{map_svg(sdn, "Sudan air temperature trend map", 300)}<br>Sudan: {ss['decreasing']} cooling (south), {ss['increasing']} warming (north)</div>
</div>{legend_svg()}
<figcaption><b>Figures 1 and 2.</b> Air temperature trend 2001 to 2025 per 55 km grid cell (NASA POWER), exactly as the app computes it. Colored cells: change proven after the false discovery correction; grey: not proven. Sudan shows the challenge&rsquo;s twist: opposite trends inside one country. Egypt median trend: {es['median_slope_per_decade']:+.2f} °C per decade.</figcaption></figure>

<figure>{series_svg(cairo)}
<figcaption><b>Figure 3.</b> Cairo, yearly mean air temperature (NASA POWER) with its Theil-Sen trend line: {ct['slope_per_decade']:+.2f} °C per decade (95% range {ct['slope_low']:+.2f} to {ct['slope_high']:+.2f}), {ct['level_name']}, luck {100 * ct['p']:.1f}%. NASA&rsquo;s weather stations around Cairo (GISTEMP, 2 x 2 degree box): {st.get('slope_per_decade', 0):+.2f} °C per decade, {st.get('level_name', '')}.</figcaption></figure>

<figure>{bars_svg([("NASA GISTEMP, whole Earth (our engine)", xc['reference']['per_decade'], "#7f8c8d"),
                   ("NASA POWER, whole Earth (our data)", xc['ours']['per_decade'], "#2e86c1"),
                   ("NASA POWER, Arctic (north of 60 N)", xc['arctic']['per_decade'], "#2e86c1"),
                   ("NASA GISTEMP stations, Egypt", 0.419, "#7f8c8d"),
                   ("NASA POWER, Egypt", 0.237, "#2e86c1")])}
<figcaption><b>Figure 4.</b> Our trend engine on independent NASA records, 2001 to 2025. It reproduces NASA GISTEMP&rsquo;s global warming (strong evidence) and the known Arctic amplification. Over Egypt the stations warm faster than POWER, about 1.7 times the global rate; the app shows both side by side instead of hiding the difference.</figcaption></figure>

<table>
<tr><th style="width:38%">Check</th><th>Result</th></tr>
<tr><td>Engine on NASA GISTEMP, world, 2001 to 2025</td><td>{xc['reference']['per_decade']:+.2f} °C per decade, strong evidence (luck below 0.1%)</td></tr>
<tr><td>NASA POWER vs NASA GISTEMP stations, direction of change</td><td>Same direction for 87% of the world&rsquo;s area; never proven in opposite directions</td></tr>
<tr><td>Egypt, 32 station areas</td><td>Stations +0.42 °C per decade, proven in 30 of 32; POWER +0.24, proven in 12</td></tr>
<tr><td>NASA POWER rain over Egypt around 2015</td><td>POWER jumps x2.6, NASA GPCP (satellites and gauges) only x1.24: the jump is in the dataset. Rain answers carry a caution; projections remove the one-time step</td></tr>
<tr><td>Crop model, held-out regions (40 crops)</td><td>AUC 0.90; trained without Egypt, Egypt&rsquo;s FAOSTAT crop list AUC 0.93</td></tr>
<tr><td>False alarms of the chosen trend test</td><td>3.3 to 7.5% on 20,000 simulated places with no trend (target 5%)</td></tr>
</table>

<h2>5. Benefits and intended impact</h2>
<ul>
<li><b>Farmers and agricultural investors:</b> &ldquo;What can I grow here in 10 years? Where is farmland gaining or losing potential?&rdquo;</li>
<li><b>Government planners:</b> &ldquo;Which farming regions are under growing climate stress and need support, which gain potential?&rdquo;</li>
<li><b>Students, journalists and citizens:</b> &ldquo;Is my city really getting hotter or drier, or is it just a few unusual years?&rdquo;</li>
</ul>
<p>Why it matters here: the Middle East and North Africa is the most water-scarce region in the world (World Bank, 2018); the Mediterranean is already about 1.5 °C warmer than pre-industrial times and warming faster than the global average (MedECC, 2020); over Egypt, NASA&rsquo;s stations show +0.42 °C per decade since 2001; and 17.5% of Egyptian workers work in agriculture (ILO estimate, 2025). The tool is free, open and honest by design: projections are never shown as forecasts and causes are never claimed.</p>
<p><b>What makes it different.</b> Most trend tools stop at a map. We add evidence you can trust (false alarms tested and controlled), a check of every trend against an independent NASA record, and the step from &ldquo;it is changing&rdquo; to &ldquo;this is what it means for what you can grow&rdquo;.</p>

<h2>6. Tools, languages and software</h2>
<table>
<tr><th style="width:30%">Part</th><th>Tools</th></tr>
<tr><td>Analysis and server</td><td>Python 3; FastAPI, Uvicorn, NumPy, pandas, PyArrow, SciPy, statsmodels, pymannkendall, ruptures, xarray, netCDF4</td></tr>
<tr><td>Crop model</td><td>XGBoost and scikit-learn (training, on Kaggle and locally); numpy runtime in the app</td></tr>
<tr><td>App</td><td>HTML, CSS and JavaScript, no build step; MapLibre GL JS 5.6 (globe), Plotly.js 2.35 (charts), polygon-clipping</td></tr>
<tr><td>Engineering</td><td>Git and GitHub, GitHub Actions (69 tests on every push), Render (hosting), Hugging Face (model), Docker file for other hosts</td></tr>
<tr><td>Hardware</td><td>Team laptops (Windows); no special hardware</td></tr>
</table>

<h2>7. Limitations</h2>
<ul>
<li>Grid cells are about 55 km: regional screening, not advice for a single farm.</li>
<li>NASA POWER warms more slowly than NASA&rsquo;s stations over Egypt, so many cells read &ldquo;not proven&rdquo;; the app shows the station trend next to it.</li>
<li>Irrigated mode assumes water can be supplied; it does not show that water exists.</li>
<li>The crop model learns where crops are grown today, which also reflects markets, policy and water, not only climate. Olive and date palm are not separate crops in the training maps.</li>
<li>Projections continue today&rsquo;s trends; they are not climate forecasts. No causes are claimed.</li>
<li>Free hosting sleeps after 15 minutes without visitors: the first visit can take about a minute.</li>
</ul>

<h2>8. Future plans</h2>
<ul>
<li>Finer satellite layers (MODIS and VIIRS at 1 km) to see single fields and towns.</li>
<li>Water availability (NASA GRACE groundwater, river flow), so irrigated answers say where water exists.</li>
<li>Heat extremes (hot days per year) next to averages, and an Arabic interface.</li>
<li>More countries for the farming tabs, and a downloadable report for planners.</li>
</ul>

<h2>9. NASA data and resources used</h2>
<table>
<tr><th style="width:30%">Resource</th><th>How we used it</th></tr>
<tr><td><a href="https://power.larc.nasa.gov">NASA POWER</a> (MERRA-2 based), monthly, 2001 to 2025</td><td>The data behind every map, chart and crop score: T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, GWETTOP, GWETROOT</td></tr>
<tr><td><a href="https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/">NASA GMAO MERRA-2</a></td><td>The reanalysis that NASA POWER is built on</td></tr>
<tr><td><a href="https://data.giss.nasa.gov/gistemp/">NASA GISTEMP v4</a> (global means and 250 km station grid)</td><td>Validation of our trend engine; the weather station line shown next to air temperature answers</td></tr>
<tr><td>GPCP v2.3 monthly precipitation (NASA GSFC led; <a href="https://psl.noaa.gov/data/gridded/data.gpcp.html">data from NOAA PSL</a>)</td><td>Independent rain check that found the 2015 step in POWER rain</td></tr>
<tr><td><a href="https://earthdata.nasa.gov/gibs">NASA GIBS</a> (Blue Marble, VIIRS)</td><td>Imagery of the globe</td></tr>
</table>

<h2>10. Other data, references and credits</h2>
<table>
<tr><th style="width:36%">Resource</th><th>Use and credit</th></tr>
<tr><td><a href="https://doi.org/10.7910/DVN/SWPENT">IFPRI MapSPAM 2020 v2r2</a>, CC BY 4.0</td><td>Where crops are grown: training labels of the crop model. <i>This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no responsibility for the analyses or interpretations of the data presented here.</i></td></tr>
<tr><td><a href="https://www.fao.org/faostat/">FAOSTAT</a> (FAO)</td><td>Checking the model against Egypt&rsquo;s real crop list</td></tr>
<tr><td><a href="https://ecocrop.apps.fao.org/ecocrop/srv/en/home">FAO ECOCROP</a></td><td>First crop calculator (kept as a fallback)</td></tr>
<tr><td><a href="https://www.naturalearthdata.com">Natural Earth</a> (public domain)</td><td>Country borders and cities for search; the map names Palestine and places the Golan Heights in Syria</td></tr>
<tr><td><a href="https://s2maps.eu">Sentinel-2 cloudless 2020 by EOX</a></td><td>Close-up imagery (contains modified Copernicus Sentinel data 2020)</td></tr>
<tr><td>World Bank (2018), <a href="https://openknowledge.worldbank.org/handle/10986/27659">Beyond Scarcity</a>; MedECC (2020), <a href="https://www.medecc.org">MAR1</a>; <a href="https://ourworldindata.org/grapher/share-of-the-labor-force-employed-in-agriculture">Our World in Data</a> (ILO)</td><td>Impact facts</td></tr>
<tr><td>Methods literature</td><td>Mann (1945); Kendall (1975); Sen (1968); Hamed and Rao (1998); Yue and Wang (2004); Benjamini and Hochberg (1995); Pettitt (1979); Chen and Guestrin (2016, XGBoost); Lenssen et al. (2019, GISTEMP); Adler et al. (2018, GPCP)</td></tr>
<tr><td>Open source code</td><td>FastAPI, Uvicorn, NumPy, pandas, PyArrow, SciPy, statsmodels, pymannkendall, ruptures, xarray, netCDF4, scikit-learn, XGBoost, MapLibre GL JS, Plotly.js, polygon-clipping, Leaflet</td></tr>
<tr><td>Platforms</td><td>GitHub, Render, Hugging Face, Kaggle</td></tr>
</table>
<p class="small">The full list with links is in the repository: docs/REFERENCES.md.</p>

<h2>11. Use of AI (Super Intelligence) tools</h2>
<table>
<tr><th style="width:24%">Tool</th><th style="width:38%">Used for</th><th>Affected content</th></tr>
<tr><td>Claude (Anthropic)</td><td>Coding and debugging, analysis scripts and checks, research summaries, documentation and submission text drafting</td><td>Code in api/, app/, ml/, data/ and scripts/; docs/; this document (text and generated figures). Every output was reviewed and tested by the team (69 automated tests).</td></tr>
<tr><td>Manus (AI agent)</td><td>First training notebook of the crop model (v2), on Kaggle</td><td>ml/crop_model/training/; the model in the app (v3.1) was retrained from it in our repository</td></tr>
</table>
<p>The crop model itself is our own machine learning model (XGBoost) trained on public data. No language model produces any number shown in the app: every sentence is built from computed values. The figures in this document are drawn by our own script from the live app&rsquo;s answers, not generated as images by AI. No NASA logos or branding are used. AI use is also stated in the repository (docs/REFERENCES.md) and in the model card.</p>

</body></html>"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page = OUT_DIR / "CropShift_Earth_Documentation.html"
    pdf = OUT_DIR / "CropShift_Earth_Documentation.pdf"
    page.write_text(build(), encoding="utf-8")
    chrome = next((c for c in CHROME if Path(c).exists()), None)
    if not chrome:
        print(f"Wrote {page}. No Chrome or Edge found: open it in a browser and print to PDF.")
        return 1
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", page.as_uri()], check=True, timeout=180)
    print(f"Wrote {pdf} ({pdf.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
