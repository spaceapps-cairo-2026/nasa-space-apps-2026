// Trends tab (F1): result panel, chart and map colors, for lane A's contract v0.3 (contracts/api.md).
/* global Plotly */
import { borderTouchIndex, cutCell } from './geo.js';

// Friendly names, units and one-line definitions for students (the API sends codes, raw units, sources).
const VARS = {
  T2M: { name: 'Air temperature', unit: '°C', def: 'Average temperature of the air 2 meters above the ground.' },
  T2M_MAX: { name: 'Daily maximum temperature', unit: '°C', def: 'The hottest temperature of each day, averaged over the year.' },
  T2M_MIN: { name: 'Daily minimum temperature', unit: '°C', def: 'The coldest temperature of each day (usually at night), averaged over the year.' },
  PRECTOTCORR: { name: 'Rainfall', unit: 'mm per day', def: 'Rain and snow that falls, as an average depth of water per day over the year.' },
  GWETTOP: { name: 'Topsoil wetness', unit: '0 to 1', def: 'How wet the top 5 cm of soil is: 0 is completely dry, 1 is fully soaked.' },
  GWETROOT: { name: 'Root zone wetness', unit: '0 to 1', def: 'How wet the soil is down to about 1 meter, where plant roots drink: 0 is dry, 1 is soaked.' },
  RH2M: { name: 'Relative humidity', unit: '%', def: 'How much water vapor the air holds, compared with the most it could hold at that temperature.' },
};

/** Display info for a variable object or code from the API. */
export function varInfo(v) {
  const code = typeof v === 'string' ? v : v.code;
  const known = VARS[code];
  const raw = typeof v === 'string' ? {} : v;
  return {
    code,
    name: known ? known.name : (raw.name || code).replace(/^./, (c) => c.toUpperCase()),
    unit: known ? known.unit : raw.unit === 'C' ? '°C' : raw.unit || '',
    definition: known ? known.def : '',
    source: raw.source || '',
  };
}

const LEVELS = { 2: 'strong', 1: 'moderate', 0: 'not_proven' };
const LEVEL_TEXT = { strong: 'Strong evidence', moderate: 'Moderate evidence', not_proven: 'Not proven' };
const PALETTES = {
  heat: ['#2166ac', '#f2f2f2', '#b2182b'],
  water: ['#8c510a', '#f2f2f2', '#01665e'],
};
export const NOT_PROVEN_COLOR = '#7d838c';

export function paletteFor(code) { return code.startsWith('T2M') ? PALETTES.heat : PALETTES.water; }

function hex(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function mix(a, b, t) {
  const A = hex(a), B = hex(b);
  return '#' + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, '0')).join('');
}

function esc(s) { const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }

/** Decimals that keep a number of this size readable: 0.29, 0.033, 0.0044. */
function decimalsFor(x, digits = 2) {
  const a = Math.abs(x);
  return a !== 0 && a < 0.01 ? 4 : a < 0.1 ? 3 : digits;
}

function fmt(x, digits = 2) {
  if (x === null || x === undefined || Number.isNaN(x)) return 'n/a';
  return (x > 0 ? '+' : '') + x.toFixed(decimalsFor(x, digits));
}

/** Both ends of a range with the same decimals (those of the larger end): "+0.03" and "+0.51". */
function fmtRange(lo, hi) {
  const d = decimalsFor(Math.max(Math.abs(lo), Math.abs(hi)));
  const one = (x) => (x > 0 ? '+' : '') + x.toFixed(d);
  return [one(lo), one(hi)];
}

/**
 * A p-value (or q-value) as a percentage: how often a trend at least this strong shows up by luck
 * when nothing is really changing. It is NOT the chance that the trend is real.
 */
export function luckPercent(p) {
  if (p === null || p === undefined || Number.isNaN(p)) return null;
  if (p < 0.001) return 'less than 0.1%';
  const x = p * 100;
  return `${x < 9.95 ? x.toFixed(1) : Math.round(x)}%`;
}

function oneIn(p) {
  if (p < 0.001) return 'fewer than 1 in 1,000';
  if (p > 0.4) return null;
  return `about 1 in ${Math.round(1 / p).toLocaleString('en-US')}`;
}

/**
 * The "Is the change real?" box. One answer, shown two ways: the luck percentage is the number,
 * the badge is the same number in words (under 1% strong, under 5% moderate, otherwise not proven).
 */
function luckHTML(p, conf) {
  const pct = luckPercent(p);
  if (pct === null) return '';
  const odds = oneIn(p);
  const verdict = conf === 'strong' ? 'That is under 1%, so we call it <strong>strong evidence</strong> of a real change.'
    : conf === 'moderate' ? 'That is under 5%, so we call it <strong>moderate evidence</strong> of a real change.'
      : 'That is 5% or more, so luck is a reasonable explanation: the change is <strong>not proven</strong>.';
  return `<div class="luck ${conf}">
      <div class="luck-top"><span class="luck-label">Is the change real?</span><span class="badge ${conf}">${LEVEL_TEXT[conf]}</span></div>
      <p>Chance that luck alone gives a trend this strong: <strong>${pct}</strong>${odds ? ` (${odds})` : ''}.
      Even if nothing were really changing here, normal year to year ups and downs would do it that often. ${verdict}</p>
    </div>`;
}

/** The years a trend object covers: {s, e, span, whole, text}. Works with older answers that only have series. */
export function periodOf(obj, series = null) {
  const s = obj.start_year ?? (series ? series[0].t : 2001);
  const e = obj.end_year ?? (series ? series[series.length - 1].t : 2025);
  const whole = !series || (s === series[0].t && e === series[series.length - 1].t);
  return { s, e, span: e - s, whole, text: `${s} to ${e}` };
}

/** Total change over the chosen years from a rate per decade. */
export function totalChange(slopePerDecade, period) {
  return slopePerDecade === null || slopePerDecade === undefined ? null : (slopePerDecade * period.span) / 10;
}

/** The two headline numbers of a result panel: total change over the chosen years and the trend per decade. */
function headlineHTML(total, slopePerDecade, unit, per) {
  return `<div class="headline">
      <div class="stat"><div class="stat-val">${fmt(total)} <span class="stat-unit">${esc(unit)}</span></div>
        <div class="stat-lab">Total change, ${per.s} to ${per.e}</div></div>
      <div class="stat"><div class="stat-val">${fmt(slopePerDecade)} <span class="stat-unit">${esc(unit)}</span></div>
        <div class="stat-lab">Trend, per decade</div></div>
    </div>`;
}

/** Color for a proven slope, t in [-1, 1] relative to the map's range. */
function colorFor(pal, t) { return t < 0 ? mix(pal[1], pal[0], -t) : mix(pal[1], pal[2], t); }

/** Range for the color scale: 95th percentile of proven |slope|, so one extreme cell does not wash out the rest. */
function rangeOf(slopes) {
  if (!slopes.length) return 1e-9;
  const a = slopes.map(Math.abs).sort((x, y) => x - y);
  return Math.max(a[Math.floor(0.95 * (a.length - 1))], 1e-9);
}

/**
 * trend_region (lane A, compact grid) -> GeoJSON cells for the region map.
 * grid.slope_per_decade[i][j] belongs to the cell centered at grid.lats[i], grid.lons[j].
 * With a border, each cell is cut to it. Not proven cells are flat tiles; proven ones are columns.
 */
export function gridToGeoJSON(res, border = null) {
  const g = res.grid;
  const dlat = g.lat_step, dlon = g.lon_step;
  const pal = paletteFor(res.variable.code);
  const touched = border ? borderTouchIndex(border, g.lats[0], g.lons[0], dlat, dlon) : null;
  const gap = Math.min(0.025, dlon * 0.04); // thin gap so neighbouring cells read as separate
  const kept = [];
  for (let i = 0; i < g.lats.length; i++) {
    for (let j = 0; j < g.lons.length; j++) {
      const level = g.level[i][j];
      const slope = g.slope_per_decade[i][j];
      if (level === null || level < 0 || slope === null) continue;
      const lat = g.lats[i], lon = g.lons[j];
      const full = [lon - dlon / 2, lat - dlat / 2, lon + dlon / 2, lat + dlat / 2];
      const inner = [full[0] + gap, full[1] + gap, full[2] - gap, full[3] - gap];
      const geometry = border
        ? cutCell(full, inner, border, touched, `${i},${j}`)
        : { type: 'Polygon', coordinates: [[[inner[0], inner[1]], [inner[2], inner[1]], [inner[2], inner[3]], [inner[0], inner[3]], [inner[0], inner[1]]]] };
      if (geometry) kept.push({ lat, lon, slope, q: g.q ? g.q[i][j] : null, confidence: LEVELS[level], geometry });
    }
  }
  const range = rangeOf(kept.filter((c) => c.confidence !== 'not_proven').map((c) => c.slope));
  const counts = { increasing: 0, decreasing: 0, not_proven: 0, total: kept.length };
  const features = kept.map((c) => {
    let color = NOT_PROVEN_COLOR, height = 0;
    if (c.confidence === 'not_proven') counts.not_proven += 1;
    else {
      const t = Math.max(-1, Math.min(1, c.slope / range));
      color = colorFor(pal, t);
      height = 6000 + 50000 * Math.abs(t);
      counts[c.slope > 0 ? 'increasing' : 'decreasing'] += 1;
    }
    return { type: 'Feature', properties: { lat: c.lat, lon: c.lon, slope: c.slope, q: c.q, confidence: c.confidence, color, height, flat: c.confidence === 'not_proven' }, geometry: c.geometry };
  });
  return { range, counts, fc: { type: 'FeatureCollection', features } };
}

const MERC_MAX_LAT = 85.0511;

/**
 * trend_world (lane A, compact grid) -> an image for MapLibre. The grid is in latitude steps, MapLibre
 * images are stretched in Web Mercator, so rows are resampled to Mercator here.
 * Proven warming red, proven cooling blue, not proven left clear so the planet shows through.
 */
export function worldImage(res) {
  const g = res.grid;
  const lat0 = g.lats[0], lon0 = g.lons[0], dlat = g.lat_step, dlon = g.lon_step;
  const nrows = g.lats.length, ncols = g.lons.length;
  const pal = paletteFor(res.variable.code).map(hex);
  const proven = [];
  for (let i = 0; i < nrows; i++) for (let j = 0; j < ncols; j++) if (g.level[i][j] > 0) proven.push(g.slope_per_decade[i][j]);
  const range = rangeOf(proven);
  const W = ncols, H = Math.max(360, nrows * 2);
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const img = ctx.createImageData(W, H);
  for (let y = 0; y < H; y++) {
    const merc = Math.PI * (1 - (2 * (y + 0.5)) / H);
    const lat = (Math.atan(Math.sinh(merc)) * 180) / Math.PI;
    const i = Math.round((lat - lat0) / dlat);
    if (i < 0 || i >= nrows) continue;
    for (let j = 0; j < W; j++) {
      const level = g.level[i][j];
      if (!(level > 0)) continue;
      const t = Math.max(-1, Math.min(1, g.slope_per_decade[i][j] / range));
      const [a, b] = t < 0 ? [pal[1], pal[0]] : [pal[1], pal[2]];
      const u = 0.3 + 0.7 * Math.abs(t); // start at a visible tint: proven but small is never near-white
      const o = (y * W + j) * 4;
      img.data[o] = a[0] + (b[0] - a[0]) * u;
      img.data[o + 1] = a[1] + (b[1] - a[1]) * u;
      img.data[o + 2] = a[2] + (b[2] - a[2]) * u;
      img.data[o + 3] = level === 2 ? 215 : 160;
    }
  }
  ctx.putImageData(img, 0, 0);
  // MapLibre cannot place an image that starts past the date line, so snap the half-cell
  // offset to exactly -180 / +180 (invisible at world scale).
  const west = Math.max(-180, lon0 - dlon / 2), east = west + 360;
  return {
    url: canvas.toDataURL('image/png'),
    coordinates: [[west, MERC_MAX_LAT], [east, MERC_MAX_LAT], [east, -MERC_MAX_LAT], [west, -MERC_MAX_LAT]],
    range,
  };
}

export function legendHTML(variable, range, kind = 'region', period = null) {
  const v = varInfo(variable);
  const pal = paletteFor(v.code);
  // The map is colored by rate; the scale is labeled with the total change over the chosen years.
  const r = fmt(period ? totalChange(range, period) : range).replace('+', '');
  const notes = kind === 'world'
    ? '<div class="note">Whole Earth: only proven changes are colored; clear means not proven.</div>'
    : `<div class="np"><i></i>Flat grey tile: not proven, could be normal year to year variation</div>
    <div class="note">Raised columns are proven changes; taller means a bigger change.</div>`;
  // No proven cell on this map: there is no color scale to show.
  if (!(range > 1e-8)) {
    return `<div class="note">${esc(v.name)}: no proven change on this map, so nothing is colored.</div>
      ${kind === 'world' ? '' : '<div class="np"><i></i>Flat grey tile: not proven, could be normal year to year variation</div>'}`;
  }
  return `<div class="note">${esc(v.name)}: ${period ? `total change, ${period.text}` : 'change per decade'} (${esc(v.unit)})</div>
    <div class="bar" style="background:linear-gradient(90deg,${pal[0]},${pal[1]},${pal[2]})"></div>
    <div class="scale"><span>-${r}</span><span>0</span><span>+${r}</span></div>
    ${notes}`;
}

function shell(panel, inner) {
  panel.hidden = false;
  panel.innerHTML = `<button class="btn close" aria-label="Close panel">×</button>${inner}`;
  panel.querySelector('.close').onclick = () => { panel.hidden = true; };
}

export function showLoading(panel, title, text = 'Asking NASA data…') {
  shell(panel, `<h2>${esc(title)}</h2><div class="loading">${esc(text)}</div>`);
}

export function showMessage(panel, title, message, kind = 'info') {
  shell(panel, `<h2>${esc(title)}</h2><div class="callout ${kind}">${esc(message)}</div>`);
}

/** trend_point (lane A) -> the result panel. */
export function showTrend(panel, res, placeLabel, mockNote = null) {
  const v = varInfo(res.variable), t = res.trend;
  const conf = LEVELS[t.level] || 'not_proven';
  const where = placeLabel || `${res.location.lat.toFixed(2)}, ${res.location.lon.toFixed(2)}`;
  const per = periodOf(t, res.series);
  const inRange = res.series.filter((s) => s.t >= per.s && s.t <= per.e);
  const used = inRange.filter((s) => s.v !== null).length;
  const total = t.change_total ?? totalChange(t.slope_per_decade, per);
  const lo = t.change_low ?? totalChange(t.slope_low, per), hi = t.change_high ?? totalChange(t.slope_high, per);
  const pTxt = t.p === null || t.p === undefined ? 'n/a' : t.p < 0.001 ? '< 0.001' : t.p.toFixed(3);
  shell(panel, `
    <h2>${esc(v.name)}</h2>
    <div class="where">${esc(where)} · trend over ${per.text}</div>
    ${mockNote ? `<div class="callout warn">${esc(mockNote)}</div>` : ''}
    ${t.level === -1 ? '<div class="callout warn">No data here: too few valid years for a trend.</div>' : `${headlineHTML(total, t.slope_per_decade, v.unit, per)}
    <p class="range"><strong>How big is the change?</strong> ${fmt(total)} is our best estimate${lo !== null && hi !== null ? `; the true change is most likely between
      <strong>${fmtRange(lo, hi)[0]}</strong> and <strong>${fmtRange(lo, hi)[1]}</strong> ${esc(v.unit)}` : ''}.</p>
    ${luckHTML(t.p, conf)}
    ${per.span + 1 < 20 ? `<p class="note">You chose ${per.span + 1} years. Short ranges rarely prove a change: there are too few years to tell it from normal ups and downs. Try a longer range.</p>` : ''}`}
    <div class="chart" id="trend-chart"></div>
    <p class="sentence">${esc(res.sentence)}</p>
    ${res.caution ? `<div class="callout warn">${esc(res.caution)}</div>` : ''}
    ${v.definition ? `<div class="callout info"><strong>What is this?</strong> ${esc(v.definition)}</div>` : ''}
    <details>
      <summary>How we know</summary>
      <dl>
        <dt>p-value</dt><dd>${pTxt}${luckPercent(t.p) ? ` (${luckPercent(t.p)})` : ''}</dd>
        <dt>Years used</dt><dd>${used} of ${inRange.length} (${per.text})</dd>
        <dt>Change starts</dt><dd>${t.change_point_year ?? 'no clear start'}</dd>
        <dt>Method</dt><dd>${esc(t.method)}</dd>
        <dt>Data</dt><dd>${esc(v.source)}${res.data_from ? ` (${esc(res.data_from)})` : ''}</dd>
      </dl>
      <p>The panel answers two different questions.</p>
      <p><strong>1. Is the change real?</strong> The luck percentage (the p-value) is how often a trend this strong would appear if nothing were
      really changing. The label is that same number in words: under 1% is strong evidence, under 5% is moderate evidence,
      5% or more is not proven. It is not the chance that the trend is true, so we never say "97% real".</p>
      <p><strong>2. How big is the change?</strong> The "most likely between" range (a 95% range). It is about the size of the change, not
      about whether it exists. A wide range means the data is noisy; a range that includes 0 goes with "not proven".</p>
    </details>`);
  drawChart(document.getElementById('trend-chart'), res, conf);
}

/** A country's trend map is shown: its average trend as the two headline numbers, then the sentence. */
export function showRegionSummary(panel, grid, title, prefix = '') {
  const v = varInfo(grid.variable), t = grid.mean_trend;
  const per = periodOf(t || grid, grid.mean_series);
  const head = t && t.level !== -1 && t.slope_per_decade !== null && t.slope_per_decade !== undefined
    ? `<div class="where">Average over the whole area · ${per.text}</div>
      ${headlineHTML(t.change_total ?? totalChange(t.slope_per_decade, per), t.slope_per_decade, v.unit, per)}
      <span class="badge ${LEVELS[t.level] || 'not_proven'}">${LEVEL_TEXT[LEVELS[t.level] || 'not_proven']}</span>`
    : '';
  shell(panel, `<h2>${esc(title)}</h2>${head}
    <p class="sentence">${esc(prefix)}${esc(grid.mean_sentence || '')}</p>
    ${grid.caution ? `<div class="callout warn">${esc(grid.caution)}</div>` : ''}
    <div class="callout info">Click a column, or any point, to see its trend.</div>`);
}

export function showCellSummary(panel, props, variable, label, reason, period = null) {
  const v = varInfo(variable);
  const per = period || periodOf({});
  shell(panel, `
    <h2>${esc(v.name)}</h2>
    <div class="where">${esc(label)}</div>
    <span class="badge ${props.confidence}">${LEVEL_TEXT[props.confidence]}</span>
    ${headlineHTML(totalChange(Number(props.slope), per), Number(props.slope), v.unit, per)}
    <p class="range">${props.q === null || props.q === undefined ? 'No test result for this cell.'
      : `Chance of a trend this strong by luck alone, after correcting for testing many cells at once: <strong>${luckPercent(Number(props.q))}</strong>`}</p>
    <div class="callout info">${esc(reason)}</div>`);
}

function drawChart(el, res, conf) {
  const s = res.series.filter((p) => p.v !== null);
  const line = res.trend_line || [];
  const lineColor = conf === 'not_proven' ? '#9aa3ae' : '#ffcc66';
  const cp = res.trend.change_point_year;
  const per = periodOf(res.trend, res.series);
  const shapes = cp ? [{ type: 'line', x0: cp, x1: cp, yref: 'paper', y0: 0, y1: 1, line: { color: 'rgba(255,204,102,.6)', width: 1.5, dash: 'dot' } }] : [];
  // Chosen years highlighted when they are not the whole record.
  if (!per.whole) shapes.push({ type: 'rect', x0: per.s - 0.5, x1: per.e + 0.5, yref: 'paper', y0: 0, y1: 1, fillcolor: 'rgba(111,211,255,.10)', line: { width: 0 }, layer: 'below' });
  const height = cp ? 236 : 222;
  el.style.height = `${height}px`;   // the box takes the chart's real height, so nothing below is covered
  Plotly.newPlot(el, [
    { x: s.map((p) => p.t), y: s.map((p) => p.v), mode: 'lines+markers', name: 'Yearly average',
      line: { color: '#6fd3ff', width: 2 }, marker: { size: 5 }, hovertemplate: '%{x}: %{y:.2f}<extra></extra>' },
    { x: line.map((p) => p.t), y: line.map((p) => p.v), mode: 'lines', name: 'Trend',
      line: { color: lineColor, width: 2.5, dash: 'dash' }, hoverinfo: 'skip' },
  ], {
    // Room above the plot for the "change starts" label (it sits just above the top edge).
    margin: { l: 44, r: 10, t: cp ? 24 : 10, b: 28 }, height,
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#9aabc2', size: 11 },
    xaxis: { gridcolor: 'rgba(255,255,255,0.06)', zeroline: false },
    yaxis: { gridcolor: 'rgba(255,255,255,0.08)', zeroline: false, title: { text: varInfo(res.variable).unit, standoff: 6 } },
    shapes,
    annotations: cp ? [{ x: cp, yref: 'paper', y: 1, text: `change starts ${cp}`, showarrow: false, font: { size: 10, color: '#ffcc66' }, yanchor: 'bottom' }] : [],
    showlegend: false,
  }, { displayModeBar: false, responsive: true });
  // Redraw at the new width whenever the panel changes size (window resized, phone turned, layout switched);
  // Plotly's own option only listens to the window and missed the panel's switch between layouts.
  if (window.ResizeObserver) {
    let last = el.clientWidth;
    new ResizeObserver(() => {
      if (el.isConnected && el.clientWidth && el.clientWidth !== last) { last = el.clientWidth; Plotly.Plots.resize(el); }
    }).observe(el);
  }
}
