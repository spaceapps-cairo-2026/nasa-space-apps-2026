"""Build the project documentation (Cairo local submission form) as a LaTeX paper and its PDF:
docs/documentation/CropShift_Earth_Documentation.tex and .pdf

    python scripts/make_documentation.py            numbers and figures from the live app (Render)
    python scripts/make_documentation.py --local    from a local server at http://localhost:8000
    python scripts/make_documentation.py --tex-only write the .tex (and the screenshot) without compiling

The team laptops have no LaTeX, so the .tex is compiled by the free LaTeX-on-HTTP service (latex.ytotech.com).
The same .tex compiles unchanged on Overleaf (upload it with app_welcome.png).
Figures are TikZ/pgfplots drawn from the API's answers at build time; text numbers match docs/SUBMISSION.md.
"""
from __future__ import annotations

import base64
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "documentation"
API = "http://localhost:8000" if "--local" in sys.argv else "https://cropshift-earth.onrender.com"
COMPILER = "https://latex.ytotech.com/builds/sync"
SHOT = "app_welcome.png"


def get(path: str) -> dict:
    with urllib.request.urlopen(API + path, timeout=180) as r:
        return json.load(r)


def region(iso: str, boxes: dict) -> dict:
    w, s, e, n = boxes[iso]
    return get(f"/api/trend/region?lat_min={s}&lat_max={n}&lon_min={w}&lon_max={e}&variable=T2M&country={iso}")


# ---------- figures (TikZ) ----------

def tikz_map(d: dict, width_cm: float) -> str:
    """One filled square per grid cell: red/blue shade = proven warming/cooling, grey = not proven."""
    g = d["grid"]
    lats, lons = g["lats"], g["lons"]
    dlat, dlon = g["lat_step"], g["lon_step"]
    k = width_cm / ((max(lons) - min(lons)) + dlon)
    lat0, lon0 = min(lats), min(lons)
    out = []
    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            lev = g["level"][i][j]
            if lev is None or lev < 0:
                continue
            slope = g["slope_per_decade"][i][j]
            if lev >= 1 and slope is not None:
                pct = max(25, min(100, round(abs(slope) / 0.6 * 100)))
                color = f"{'red' if slope > 0 else 'blue'}!{pct}!white"
            else:
                color = "black!14"
            out.append(f"\\fill[{color}] ({(lon - lon0) * k:.3f},{(lat - lat0) * k:.3f}) "
                       f"rectangle ++({dlon * k + .004:.3f},{dlat * k + .004:.3f});")
    return "\\begin{tikzpicture}\n" + "\n".join(out) + "\n\\end{tikzpicture}"


def tikz_legend() -> str:
    stops = [-0.6, -0.4, -0.2, 0.2, 0.4, 0.6]
    parts = []
    for n, v in enumerate(stops):
        pct = max(25, min(100, round(abs(v) / 0.6 * 100)))
        color = f"{'red' if v > 0 else 'blue'}!{pct}!white"
        parts.append(f"\\fill[{color}] ({n * 1.1:.2f},0) rectangle ++(1.1,0.3); "
                     f"\\node[below, font=\\scriptsize] at ({n * 1.1 + .55:.2f},0) {{{v:+.1f}}};")
    parts.append("\\fill[black!14] (7.2,0) rectangle ++(0.5,0.3); \\node[right, font=\\scriptsize] at (7.7,0.15) {not proven};")
    parts.append("\\node[font=\\scriptsize, anchor=west] at (0,-0.75) {proven trend, \\degC{} per decade (blue: cooling, red: warming)};")
    return "\\begin{tikzpicture}\n" + "\n".join(parts) + "\n\\end{tikzpicture}"


def pgf_series(point: dict) -> str:
    pts = " ".join(f"({p['t']},{p['v']:.3f})" for p in point["series"])
    tl = point["trend_line"]
    line = f"({tl[0]['t']},{tl[0]['v']:.3f}) ({tl[-1]['t']},{tl[-1]['v']:.3f})"
    return ("\\begin{tikzpicture}\n\\begin{axis}[width=0.92\\linewidth, height=5.2cm, xmin=2000.3, xmax=2025.7,\n"
            "  xlabel={Year}, ylabel={Air temperature (\\degC)}, xtick={2001,2005,...,2025},\n"
            "  x tick label style={/pgf/number format/1000 sep={}}, ymajorgrids, grid style={black!10},\n"
            "  legend style={font=\\footnotesize, draw=none, at={(0.5,-0.3)}, anchor=north, legend columns=2, /tikz/every even column/.append style={column sep=12pt}}, tick label style={font=\\footnotesize}]\n"
            f"\\addplot[black!45, thin, mark=*, mark size=1.3pt, mark options={{fill=blue!60!black, draw=blue!60!black}}] coordinates {{{pts}}};\n"
            "\\addlegendentry{yearly mean, NASA POWER}\n"
            f"\\addplot[red!75!black, thick] coordinates {{{line}}};\n"
            "\\addlegendentry{Theil--Sen trend}\n\\end{axis}\n\\end{tikzpicture}")


def tikz_bars(rows: list[tuple[str, float, str]]) -> str:
    vmax = max(v for _, v, _ in rows)
    out = []
    for n, (label, v, color) in enumerate(rows):
        y = -n * 0.62
        w = 6.0 * v / vmax
        out.append(f"\\node[anchor=east, font=\\small] at (-0.15,{y + .2:.2f}) {{{label}}};"
                   f"\\fill[{color}] (0,{y:.2f}) rectangle ({w:.2f},{y + .4:.2f});"
                   f"\\node[anchor=west, font=\\small] at ({w + .08:.2f},{y + .2:.2f}) {{$+{v:.2f}$}};")
    return "\\begin{tikzpicture}\n" + "\n".join(out) + "\n\\end{tikzpicture}"


# ---------- the paper ----------

TEMPLATE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=2.4cm]{geometry}
\usepackage{microtype}
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{xcolor}
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usepackage{textcomp}
\usepackage[font=small,labelfont=bf]{caption}
\usepackage{enumitem}
\setlist{itemsep=1pt,topsep=3pt}
\usepackage{xurl}
\usepackage[colorlinks=true,linkcolor=blue!50!black,urlcolor=blue!50!black,citecolor=blue!50!black]{hyperref}
\newcommand{\degC}{\,\textdegree{}C}
\renewcommand{\arraystretch}{1.15}

\title{\textbf{CropShift Earth}\\[4pt]
\large Separating real climate trends from year-to-year noise,\\ and what they mean for crops in the Middle East and North Africa}
\author{Team Tech Ghosts\\[2pt]
\normalsize NASA Space Apps Challenge 2026, Cairo\\
\normalsize Challenge: \emph{Be An Earth System Trend Detective!}}
\date{15 November 2026}

\begin{document}
\maketitle

\begin{abstract}
\noindent A few unusually hot summers do not make a trend, yet most climate dashboards leave it to the reader to tell the two apart. We built CropShift Earth, a web globe that takes 25 years of monthly NASA POWER data (2001 to 2025) and, for any place, country or the whole Earth, reports how fast a variable is changing, where, since when, and how strong the statistical evidence is. Significance is tested with a Mann--Kendall test whose variance is corrected for year-to-year persistence, and every map is controlled for false discoveries. We chose this method by simulation: of seven candidates it kept false alarms close to the nominal 5\% while losing much less detection power than pre-whitening. The trend engine reproduces NASA GISTEMP's global warming rate ($+0.25$\degC{} per decade, $p<0.001$) and agrees in direction with NASA's station record over 87\% of the Earth's area. For 20 countries of the Middle East and North Africa we then ask a practical question: which of 40 crops fit a place today, and in 2030 and 2035 if current trends continue? A gradient-boosted model trained on where crops are grown worldwide answers it with a held-out AUC of 0.90.
\end{abstract}

\begin{center}\small
\begin{tabularx}{0.94\linewidth}{@{}lX@{}}
\toprule
\textbf{Live app} & \url{https://cropshift-earth.onrender.com} \\
\textbf{Project page} & \url{https://www.spaceappschallenge.org/2026/find-a-team/tech-ghosts/} \\
\textbf{Demo video} & linked on the project page (30 seconds) \\
\textbf{Source code} & \url{https://github.com/spaceapps-cairo-2026/nasa-space-apps-2026} \\
\textbf{Crop model} & \url{https://huggingface.co/OmarGhost2005/cropshift-earth-crop-model} \\
\textbf{API documentation} & \url{https://cropshift-earth.onrender.com/docs} \\
\bottomrule
\end{tabularx}
\end{center}

\section{Introduction}

Ask a farmer near Asyut whether summers are getting hotter and the answer will usually be yes. Ask whether the change is real or just a run of bad years, and the honest answer is that nobody has checked. Climate records are noisy: a single El Ni\~no year, a heat wave or a dry winter can move a 25-year average more than a decade of slow warming does. Drawing a straight line through the data is easy. Deciding whether that line means anything is the hard part, and it is the part most public tools skip.

The question matters more in some places than in others. The Middle East and North Africa is the most water-scarce region in the world \cite{worldbank2018}, the Mediterranean basin is already about 1.5\degC{} warmer than in pre-industrial times \cite{medecc2020}, and in Egypt 17.5\% of all workers are employed in agriculture \cite{owid}. For a farmer, an investor or a ministry, ``the climate is changing'' is not enough. They need to know where the change is established, how large it is, and what it implies for the crops they grow.

The challenge \emph{Be An Earth System Trend Detective!} asks for a tool that lets users choose variables from NASA missions or models, see how they change over time, and determine what is changing, where, by how much, and whether the change is significant. It also points out that one physical process can push the same variable in opposite directions in different regions. CropShift Earth answers each of these questions for any place on Earth, and adds one step that we think is missing from most trend tools: translating established trends into crop suitability for the region we live in. Our main contributions are:
\begin{itemize}
\item a trend engine whose false-alarm rate we measured before choosing it, applied with false discovery control to every map;
\item an independent check of our results against NASA's station and satellite records, including a data problem we found and handled;
\item a crop suitability outlook for 40 crops in 20 countries, today and under continued trends to 2035.
\end{itemize}

\section{Data}

\paragraph{NASA POWER.} All maps, charts and crop scores are computed from NASA POWER monthly data \cite{power}, which is derived from NASA's MERRA-2 reanalysis \cite{gelaro2017} on a $0.5^\circ \times 0.625^\circ$ grid (about 55\,km). We use six variables for 2001 to 2025: air temperature at 2\,m (\texttt{T2M}), its daily maximum (\texttt{T2M\_MAX}), precipitation (\texttt{PRECTOTCORR}), relative humidity (\texttt{RH2M}) and surface and root-zone soil wetness (\texttt{GWETTOP}, \texttt{GWETROOT}); daily minimum temperature (\texttt{T2M\_MIN}) is used for single points. Monthly values are averaged into yearly means before any test. Data for a new region are fetched from NASA on first use and cached; Egypt and a global air temperature grid ship with the application.

\paragraph{Independent records.} To check our results we use NASA GISTEMP v4 \cite{lenssen2019}, both the global mean and the 250\,km gridded station anomalies, and the GPCP v2.3 monthly precipitation analysis, which combines satellites and rain gauges \cite{adler2018}.

\paragraph{Crops.} Where crops are grown today comes from IFPRI's MapSPAM 2020 v2r2 \cite{spam2020}, aggregated onto the POWER grid (22,450 farmland cells on every continent). FAOSTAT's list of crops grown in Egypt \cite{faostat} is used only as an independent check. Country borders and city names come from Natural Earth, and the globe uses NASA GIBS imagery.

\section{Methods}

\subsection{Rate of change}
For each grid cell or point we estimate the rate of change with the Theil--Sen slope \cite{sen1968}, the median of all pairwise slopes between years. It is robust to the one-off extreme years that are common in this kind of data. We report it per decade, in the variable's own units, with a 95\% confidence range.

\subsection{Is the change real?}
We test for a monotonic trend with the Mann--Kendall test \cite{mann1945,kendall1975}. Yearly climate series are often persistent (a warm year tends to follow a warm year), which makes the plain test report trends that are not there. We therefore scale the test's variance by an effective sample size derived from the lag-1 autocorrelation \cite{hamed1998,yue2004}. For series of 20 years or more the autocorrelation is measured on the residuals from a quadratic fit, so that a change that bends (flat, then rising) is not mistaken for persistence.

A map tests hundreds of cells at once, and at the 5\% level about one cell in twenty would look significant by chance alone. We control this with the Benjamini--Hochberg false discovery rate \cite{bh1995}, as recommended for climate maps by Wilks \cite{wilks2016}. The app reports three levels: \emph{strong evidence} ($q<0.01$), \emph{moderate evidence} ($q<0.05$) and \emph{not proven}. The number itself is always shown, phrased as ``Could this be luck?'': how often a trend this strong would appear if nothing were changing. ``Not proven'' is never presented as ``no change''. Finally, the Pettitt test \cite{pettitt1979} estimates the year a shift started when there is one ($p<0.05$).

\subsection{How we chose the method}
We did not want to pick a test because it is popular. We generated 20,000 synthetic 25-year series, with and without a trend and with different degrees of persistence $\rho$, and ran seven candidate methods on them. Table~\ref{tab:methods} shows part of the outcome. The plain test and the widely used Hamed--Rao correction raise false alarms in about a quarter of trendless series once persistence is strong. Pre-whitening keeps false alarms low but finds fewer than a third of real trends. The effective-sample-size correction we use stays between 3.3\% and 8.8\% and still finds two thirds of the stronger trends, the best balance among the methods we compared on both measures. The price is caution: with only 25 years, a real but small trend is often reported as not proven.

\begin{table}[h]\centering\small
\caption{Candidate trend tests on 20,000 synthetic 25-year series. False alarms: share of trendless series called significant at $p<0.05$ (fair value 5\%). Detection: share of series with a real trend (total change 2.5 times the yearly noise, $\rho=0.3$) that are found.}\label{tab:methods}
\begin{tabular}{@{}lccc@{}}
\toprule
Method & False alarms, $\rho=0$ & False alarms, $\rho=0.6$ & Detection \\
\midrule
Plain Mann--Kendall & 4.5\% & 28.2\% & 88.5\% \\
Hamed--Rao, all lags & 7.9\% & 25.2\% & 86.2\% \\
Pre-whitening & 3.8\% & 5.3\% & 29.6\% \\
Trend-free pre-whitening & 4.5\% & 34.3\% & -- \\
Effective sample size (chosen) & 3.3\% & 8.8\% & 67.0\% \\
\bottomrule
\end{tabular}
\end{table}

\subsection{Crop suitability model}
For each of 40 crops we trained an XGBoost classifier \cite{chen2016} to tell grid cells where the crop is grown (at least 2\% of the harvested area, or 500\,ha) from cells where it is absent. Each cell is described by ten climate features computed from all six POWER variables (for example mean and coldest-month temperature, hottest monthly maximum, annual rainfall and its seasonality, humidity and soil wetness) plus the share of irrigated land. Irrigation is an input, so the same model answers both ``irrigated'' and ``rain only''. Deserts with almost no rain were added as counter-examples, and in rain-only mode scores fade to zero below 100\,mm of rain a year, because no crop is grown on rain alone there. Models were selected by spatial block cross-validation on $10^\circ \times 10^\circ$ blocks, so that the score always comes from regions the model did not see. The 8,000 trees are packed into a small file that runs with NumPy alone.

\subsection{Projections}
Each of the ten climate features is extended along its own 2001--2025 Theil--Sen trend to 2030 and 2035, and the crop model is applied to the projected climate. A 95\% range comes from 200 block-bootstrap resamples of the years. These are explicitly scenarios of the form ``if current trends continue'', not forecasts. For rain, humidity and soil wetness we first remove a one-time step in the POWER record around 2015 (Section~\ref{sec:rain}).

\section{Implementation}
The analysis is written in Python and served by a FastAPI application whose endpoints are documented online. The interface is a browser application (MapLibre GL JS globe, Plotly charts, plain JavaScript) with four tabs: Trends, Crops, Farmland and Decisions, plus a page explaining the methods and a 60-second guided tour (Figure~\ref{fig:app}). Sixty-nine automated tests run on every change. The application is hosted on Render and the crop model is published on Hugging Face.

\begin{figure}[h]\centering
\includegraphics[width=0.9\linewidth]{<<SHOT>>}
\caption{Start screen of the live application. The left panel already reports the global result for air temperature, 2001 to 2025: <<WORLD>>.}\label{fig:app}
\end{figure}

\noindent All of the following works in the deployed version: point and city trends anywhere on Earth with the matching station trend for air temperature; trend maps for any country or region; the whole-Earth layer; any period of at least ten years between 2001 and 2025; and the three farming tabs for 20 countries from Morocco to Iran.

\section{Results}

\subsection{Agreement with independent NASA records}
Run on NASA GISTEMP, our engine finds global warming of $+0.25$\degC{} per decade for 2001--2025 with strong evidence ($p<0.001$). On POWER the global rate is lower, $+0.17$\degC{} per decade (moderate evidence, $p=0.046$), and the Arctic warms fastest at $+0.35$\degC{} per decade, the well-known Arctic amplification (Figure~\ref{fig:bars}). Comparing POWER with the GISTEMP station grid area by area, the two records agree on the direction of change over 87\% of the Earth's area and are never both significant in opposite directions.

\begin{figure}[h]\centering
<<BARS>>
\caption{Trends in air temperature, 2001--2025, \degC{} per decade, all computed with our engine. Grey: NASA GISTEMP (weather stations); blue: NASA POWER (the data used in the app).}\label{fig:bars}
\end{figure}

Over Egypt the difference between the two records is noticeable. The stations warm by $+0.42$\degC{} per decade and the trend is proven in 30 of 32 station areas; POWER warms by $+0.24$\degC{} per decade and proves it in 12. In other words POWER is conservative here, and many cells read ``not proven'' that the stations would call warming. Rather than hide this, the app shows the station trend next to every air temperature answer.

\subsection{Egypt and Sudan}
Figure~\ref{fig:maps} shows the air temperature trend for every grid cell of Egypt and Sudan. In Egypt <<EGY_UP>> of <<EGY_N>> cells show proven warming and none show cooling (median trend $<<EGY_MED>>$\degC{} per decade); the proven cells follow the Nile valley, the Delta and the Red Sea coast. In Cairo the yearly mean rose by $<<CAI_RATE>>$\degC{} per decade (95\% range $<<CAI_LO>>$ to $<<CAI_HI>>$, <<CAI_LEVEL>>), while the surrounding station record shows $<<STA_RATE>>$\degC{} per decade with <<STA_LEVEL>> (Figure~\ref{fig:cairo}).

Sudan illustrates the challenge's point about opposite trends. Air temperature has fallen with proven evidence in <<SDN_DOWN>> cells in the south and risen in <<SDN_UP>> cells in the north, inside one country and over the same years. We do not attribute a cause here, which would need the rain and soil records alongside, but this is exactly the kind of contrast that a single national average would hide.

\begin{figure}[h]\centering
\begin{minipage}[b]{0.43\linewidth}\centering
<<MAP_EGY>>\\[3pt]\small (a) Egypt
\end{minipage}\hfill
\begin{minipage}[b]{0.53\linewidth}\centering
<<MAP_SDN>>\\[3pt]\small (b) Sudan
\end{minipage}\\[8pt]
<<LEGEND>>
\caption{Air temperature trend 2001--2025 per 55\,km grid cell (NASA POWER), after false discovery control. Coloured cells: proven trend; grey: not proven.}\label{fig:maps}
\end{figure}

\begin{figure}[h]\centering
<<SERIES>>
\caption{Cairo: yearly mean air temperature from NASA POWER and its Theil--Sen trend.}\label{fig:cairo}
\end{figure}

\subsection{A problem in the rain record}\label{sec:rain}
While checking rainfall we found that POWER's precipitation over Egypt's farmland jumps around 2015: the mean after 2015 is about 2.6 times the mean before (Pettitt test, $p<0.001$). GPCP, which uses satellites and gauges, rises only 1.24 times at the same places. The jump is therefore in the dataset rather than in the sky. A naive trend test would have reported a dramatic, ``highly significant'' increase in rain. Instead, every rain answer in the app carries a caution, and the crop projections remove this one-time step before measuring the trend.

\subsection{Crop suitability}
Table~\ref{tab:crop} summarises the crop model on regions held out of training. Trained without any Egyptian data, it still separates the crops Egypt grows from those it does not (FAOSTAT) with an AUC of 0.93. Where Egypt actually grows them, irrigated scores (0 to 100) are high for the main crops: wheat 94, tomato 90, maize 79 and rice 75. Under continued trends the average change in crop scores on Egypt's farmland by 2035 is small, about 1.3 points. The model does not represent water supply, so this should not be read as an absence of risk for Egyptian farming.

\begin{table}[h]\centering\small
\caption{Crop model performance on held-out regions, mean over 40 crops.}\label{tab:crop}
\begin{tabular}{@{}lc@{}}
\toprule
Measure & Value \\
\midrule
AUC, all / irrigated / rain-fed farmland & 0.90 / 0.85 / 0.88 \\
Worst single crop, AUC & 0.82 \\
True skill statistic / Brier score / calibration error & 0.64 / 0.13 / 0.04 \\
Trained without Egypt: Egypt's crop list (FAOSTAT), AUC & 0.93 \\
Rain only: crops rated suitable in unfarmed deserts & 0 \\
\bottomrule
\end{tabular}
\end{table}

\section{Discussion and limitations}
The main strength of the approach is that a ``proven'' label has a measured meaning: we know how often our test raises a false alarm, and every map is corrected for testing many places at once. The price is caution. Over a 25-year record with realistic persistence, moderate trends are often not proven, and in Egypt POWER is more conservative than the station record. We think it is better to say ``not proven'' and show the station evidence than to colour the whole country red.

There are several limitations. The grid cells are about 55\,km wide, so the tool is suited to regional screening rather than decisions about a single farm. Irrigated mode assumes water can be supplied and does not show whether it exists. The crop model learns where crops are grown today, which reflects markets, policy and water as well as climate, and olive and date palm are not separate crops in MapSPAM. Projections only continue present trends and are not climate forecasts. Finally, the free hosting sleeps after 15 minutes without visitors, so the first visit can take about a minute.

\section{Future work}
The next steps are finer satellite layers (MODIS and VIIRS at 1\,km) to see individual fields and towns; water availability from NASA GRACE groundwater and river records, so that irrigated answers can say where water exists; heat extremes, such as the number of very hot days, next to the averages; an Arabic interface; and more countries for the farming tabs.

\section{Conclusion}
CropShift Earth answers the challenge's questions (what is changing, where, how much and whether it is significant) for any place on Earth, and it shows opposite trends inside a single country. Its statistics were chosen on evidence and checked against independent NASA records, which also revealed a problem in the rain data that would otherwise have produced a false result. By linking established trends to crop suitability for 20 countries, it turns a climate question into one that farmers and planners in our region can act on.

\section*{Data and resources}
\small
\begin{tabularx}{\linewidth}{@{}p{0.34\linewidth}X@{}}
\toprule
\multicolumn{2}{@{}l}{\textbf{NASA data}} \\
\midrule
NASA POWER, monthly, 2001--2025 & All maps, charts and crop scores. \url{https://power.larc.nasa.gov} \\
NASA GMAO MERRA-2 & Reanalysis behind POWER. \url{https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/} \\
NASA GISTEMP v4 & Validation; station trend shown in the app. \url{https://data.giss.nasa.gov/gistemp/} \\
GPCP v2.3 (NASA GSFC led) & Independent rain check. \url{https://psl.noaa.gov/data/gridded/data.gpcp.html} \\
NASA GIBS & Globe imagery (Blue Marble, VIIRS). \url{https://earthdata.nasa.gov/gibs} \\
\midrule
\multicolumn{2}{@{}l}{\textbf{Other data and resources}} \\
\midrule
IFPRI MapSPAM 2020 v2r2 (CC BY 4.0) & Crop model labels. \url{https://doi.org/10.7910/DVN/SWPENT}. \emph{This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no responsibility for the analyses or interpretations of the data presented here.} \\
FAOSTAT; FAO ECOCROP & Crop list check; first crop calculator. \url{https://www.fao.org/faostat/} \\
Natural Earth & Borders and cities. \url{https://www.naturalearthdata.com} \\
Sentinel-2 cloudless by EOX & Close-up imagery (contains modified Copernicus Sentinel data 2020). \url{https://s2maps.eu} \\
Software & Python, FastAPI, NumPy, pandas, SciPy, statsmodels, pymannkendall, XGBoost, scikit-learn, MapLibre GL JS, Plotly.js; GitHub, Render, Hugging Face, Kaggle. Full list: \texttt{docs/REFERENCES.md} in the repository. \\
\bottomrule
\end{tabularx}
\normalsize

\section*{Use of AI tools}
We used AI assistants during the hackathon and state where. Claude (Anthropic) helped write and debug code across the analysis, server and interface, drafted analysis scripts and checks, summarised background research and helped draft documentation, including this report. Manus, an AI agent, wrote the first training notebook of the crop model on Kaggle; the model used in the app was retrained from it in our repository. All AI-assisted code and text were reviewed by the team and the code is covered by automated tests. The crop model itself is a conventional machine learning model trained by us on public data, and no language model generates any number shown in the app: every sentence is assembled from computed values. The figures in this report are drawn by our own script from the live application's results. No NASA logos or branding are used.

\begin{thebibliography}{99}\small
\bibitem{adler2018} R.\,F. Adler et al. The Global Precipitation Climatology Project (GPCP) monthly analysis (new version 2.3) and a review of 2017 global precipitation. \emph{Atmosphere}, 9(4):138, 2018.
\bibitem{bh1995} Y. Benjamini and Y. Hochberg. Controlling the false discovery rate: a practical and powerful approach to multiple testing. \emph{J. R. Stat. Soc. B}, 57:289--300, 1995.
\bibitem{chen2016} T. Chen and C. Guestrin. XGBoost: a scalable tree boosting system. In \emph{Proc. KDD}, 785--794, 2016.
\bibitem{faostat} FAO. FAOSTAT: crops and livestock products. \url{https://www.fao.org/faostat/}, accessed 2026.
\bibitem{gelaro2017} R. Gelaro et al. The Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2). \emph{J. Climate}, 30:5419--5454, 2017.
\bibitem{hamed1998} K.\,H. Hamed and A.\,R. Rao. A modified Mann--Kendall trend test for autocorrelated data. \emph{J. Hydrology}, 204:182--196, 1998.
\bibitem{kendall1975} M.\,G. Kendall. \emph{Rank Correlation Methods}. Griffin, London, 1975.
\bibitem{lenssen2019} N. Lenssen et al. Improvements in the GISTEMP uncertainty model. \emph{J. Geophys. Res. Atmos.}, 124:6307--6326, 2019.
\bibitem{mann1945} H.\,B. Mann. Nonparametric tests against trend. \emph{Econometrica}, 13:245--259, 1945.
\bibitem{medecc2020} MedECC. \emph{Climate and Environmental Change in the Mediterranean Basin: Current Situation and Risks for the Future}. First Mediterranean Assessment Report, 2020.
\bibitem{owid} Our World in Data, based on ILO modelled estimates. Share of employment in agriculture. \url{https://ourworldindata.org/grapher/share-of-the-labor-force-employed-in-agriculture}, accessed November 2026.
\bibitem{pettitt1979} A.\,N. Pettitt. A non-parametric approach to the change-point problem. \emph{Applied Statistics}, 28:126--135, 1979.
\bibitem{power} NASA Langley Research Center. Prediction Of Worldwide Energy Resources (POWER). \url{https://power.larc.nasa.gov}, accessed 2026.
\bibitem{sen1968} P.\,K. Sen. Estimates of the regression coefficient based on Kendall's tau. \emph{J. Am. Stat. Assoc.}, 63:1379--1389, 1968.
\bibitem{spam2020} International Food Policy Research Institute. Global spatially-disaggregated crop production statistics data for 2020, version 2.0 release 2 (SPAM 2020 v2r2). Harvard Dataverse, 2026. \url{https://doi.org/10.7910/DVN/SWPENT}
\bibitem{wilks2016} D.\,S. Wilks. ``The stippling shows statistically significant grid points'': how research results are routinely overstated and overinterpreted, and what to do about it. \emph{Bull. Amer. Meteor. Soc.}, 97:2263--2273, 2016.
\bibitem{worldbank2018} World Bank. \emph{Beyond Scarcity: Water Security in the Middle East and North Africa}. Washington, DC, 2018.
\bibitem{yue2004} S. Yue and C.\,Y. Wang. The Mann--Kendall test modified by effective sample size to detect trend in serially correlated hydrological series. \emph{Water Resources Management}, 18:201--218, 2004.
\end{thebibliography}

\end{document}
"""


def fmt(v: float) -> str:
    return f"{v:+.2f}"


def build_tex() -> str:
    boxes = {c["iso"]: c["bbox"] for c in get("/api/farming/countries")["countries"]}
    egy, sdn = region("EGY", boxes), region("SDN", boxes)
    cairo = get("/api/trend/point?lat=30.04&lon=31.24&variable=T2M")
    val = get("/api/validation")["checks"]["cross_check"]
    es, ss = egy["summary"], sdn["summary"]
    ct, st = cairo["trend"], cairo.get("station_check") or {}
    bars = tikz_bars([("GISTEMP, whole Earth", val["reference"]["per_decade"], "black!45"),
                      ("POWER, whole Earth", val["ours"]["per_decade"], "blue!55!black"),
                      ("POWER, Arctic (north of 60\\textdegree{}N)", val["arctic"]["per_decade"], "blue!55!black"),
                      ("GISTEMP stations, Egypt", 0.419, "black!45"),
                      ("POWER, Egypt", 0.237, "blue!55!black")])
    world = "29,620 cells with proven warming, 903 with proven cooling and 177,413 not proven, out of 207,936"
    subs = {
        "<<SHOT>>": SHOT, "<<WORLD>>": world, "<<BARS>>": bars,
        "<<EGY_UP>>": str(es["increasing"]), "<<EGY_N>>": str(es["cells"]), "<<EGY_MED>>": fmt(es["median_slope_per_decade"]),
        "<<SDN_DOWN>>": str(ss["decreasing"]), "<<SDN_UP>>": str(ss["increasing"]),
        "<<CAI_RATE>>": fmt(ct["slope_per_decade"]), "<<CAI_LO>>": fmt(ct["slope_low"]), "<<CAI_HI>>": fmt(ct["slope_high"]),
        "<<CAI_LEVEL>>": f"{ct['level_name']}, $p={ct['p']:.3f}$",
        "<<STA_RATE>>": fmt(st.get("slope_per_decade", 0.0)), "<<STA_LEVEL>>": st.get("level_name", "no station data"),
        "<<MAP_EGY>>": tikz_map(egy, 6.2), "<<MAP_SDN>>": tikz_map(sdn, 7.8), "<<LEGEND>>": tikz_legend(),
        "<<SERIES>>": pgf_series(cairo),
    }
    tex = TEMPLATE
    for key, value in subs.items():
        tex = tex.replace(key, value)
    assert "<<" not in tex, "unfilled placeholder"
    return tex


def compile_pdf(tex: str, shot: Path) -> bytes:
    resources = [{"main": True, "content": tex}]
    if shot.exists():
        resources.append({"path": SHOT, "file": base64.b64encode(shot.read_bytes()).decode()})
    req = urllib.request.Request(COMPILER, data=json.dumps({"compiler": "pdflatex", "resources": resources}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tex = build_tex()
    tex_path = OUT_DIR / "CropShift_Earth_Documentation.tex"
    tex_path.write_text(tex, encoding="utf-8")
    print(f"Wrote {tex_path}")
    if "--tex-only" in sys.argv:
        return 0
    try:
        pdf = compile_pdf(tex, OUT_DIR / SHOT)
    except urllib.error.HTTPError as exc:
        log = exc.read().decode("utf-8", "replace")
        (OUT_DIR / "latex_error.log").write_text(log, encoding="utf-8")
        print(f"LaTeX failed ({exc.code}); log in docs/documentation/latex_error.log")
        return 1
    pdf_path = OUT_DIR / "CropShift_Earth_Documentation.pdf"
    pdf_path.write_bytes(pdf)
    print(f"Wrote {pdf_path} ({len(pdf) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
