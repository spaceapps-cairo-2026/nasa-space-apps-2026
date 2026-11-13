// Trends tab (F1): result panel, chart, colors for the regional map.
/* global Plotly */
import { borderTouchIndex, cutCell } from './geo.js';

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

function fmt(x, digits = 2) {
  if (x === null || x === undefined || Number.isNaN(x)) return 'n/a';
  const a = Math.abs(x);
  const d = a !== 0 && a < 0.01 ? 4 : a < 0.1 ? 3 : digits;
  return (x > 0 ? '+' : '') + x.toFixed(d);
}

const CONF = { S: 'strong', M: 'moderate', N: 'not_proven' };

/** Color for a proven slope, t in [-1, 1] relative to the map's range. */
function colorFor(pal, t) { return t < 0 ? mix(pal[1], pal[0], -t) : mix(pal[1], pal[2], t); }

/** Range for the color scale: 95th percentile of proven |slope|, so one extreme cell does not wash out the rest. */
function rangeOf(slopes) {
  if (!slopes.length) return 1e-9;
  const a = slopes.map(Math.abs).sort((x, y) => x - y);
  return Math.max(a[Math.floor(0.95 * (a.length - 1))], 1e-9);
}

/**
 * GridTrend (contracts/api.md) -> GeoJSON cells for the region map.
 * With a border, each cell is cut to it (sea and neighbour cells disappear, coast cells keep their
 * land part). Not proven cells get height 0 (flat tiles); proven ones become columns.
 */
export function gridToGeoJSON(g, border = null) {
  const { lat0, lon0, dlat, dlon, nrows, ncols } = g.grid;
  const pal = paletteFor(g.variable.code);
  const touched = border ? borderTouchIndex(border, lat0, lon0, dlat, dlon) : null;
  const gap = Math.min(0.025, dlon * 0.04); // thin gap so neighbouring cells read as separate
  const kept = [];
  for (let i = 0; i < nrows; i++) {
    for (let j = 0; j < ncols; j++) {
      const k = i * ncols + j;
      const c = g.confidence[k];
      if (c === '-') continue;
      const lat = lat0 + i * dlat, lon = lon0 + j * dlon;
      const full = [lon - dlon / 2, lat - dlat / 2, lon + dlon / 2, lat + dlat / 2];
      const inner = [full[0] + gap, full[1] + gap, full[2] - gap, full[3] - gap];
      const geometry = border
        ? cutCell(full, inner, border, touched, `${i},${j}`)
        : { type: 'Polygon', coordinates: [[[inner[0], inner[1]], [inner[2], inner[1]], [inner[2], inner[3]], [inner[0], inner[3]], [inner[0], inner[1]]]] };
      if (geometry) kept.push({ lat, lon, slope: g.slope_per_decade[k], q: g.q[k], confidence: CONF[c], geometry });
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
    return { type: 'Feature', properties: { lat: c.lat, lon: c.lon, slope: c.slope, q: c.q, confidence: c.confidence, color, height }, geometry: c.geometry };
  });
  return { range, counts, fc: { type: 'FeatureCollection', features } };
}

const MERC_MAX_LAT = 85.0511;

/**
 * GridTrend for the whole Earth -> an image for MapLibre. The grid is in latitude steps, MapLibre
 * images are stretched in Web Mercator, so rows are resampled to Mercator here.
 * Proven warming red, proven cooling blue, not proven left clear so the planet shows through.
 */
export function worldImage(g) {
  const { lat0, lon0, dlat, dlon, nrows, ncols } = g.grid;
  const pal = paletteFor(g.variable.code).map(hex);
  const proven = [];
  for (let k = 0; k < g.confidence.length; k++) if (g.confidence[k] === 'S' || g.confidence[k] === 'M') proven.push(g.slope_per_decade[k]);
  const range = rangeOf(proven);
  const W = ncols, H = 720;
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
      const k = i * ncols + j;
      const c = g.confidence[k];
      if (c !== 'S' && c !== 'M') continue;
      const t = Math.max(-1, Math.min(1, g.slope_per_decade[k] / range));
      const [a, b] = t < 0 ? [pal[1], pal[0]] : [pal[1], pal[2]];
      const u = 0.3 + 0.7 * Math.abs(t); // start at a visible tint: proven but small is never near-white
      const o = (y * W + j) * 4;
      img.data[o] = a[0] + (b[0] - a[0]) * u;
      img.data[o + 1] = a[1] + (b[1] - a[1]) * u;
      img.data[o + 2] = a[2] + (b[2] - a[2]) * u;
      img.data[o + 3] = c === 'S' ? 215 : 160;
    }
  }
  ctx.putImageData(img, 0, 0);
  // MapLibre cannot place an image that starts past the date line, so snap the 0.3 degree
  // half-cell offset to exactly -180 / +180 (invisible at world scale).
  const west = Math.max(-180, lon0 - dlon / 2), east = west + 360;
  return {
    url: canvas.toDataURL('image/png'),
    coordinates: [[west, MERC_MAX_LAT], [east, MERC_MAX_LAT], [east, -MERC_MAX_LAT], [west, -MERC_MAX_LAT]],
    range,
  };
}

export function legendHTML(variable, range, kind = 'region') {
  const pal = paletteFor(variable.code);
  const r = fmt(range).replace('+', '');
  const notes = kind === 'world'
    ? '<div class="note">Whole Earth: only proven changes are colored; clear means not proven.</div>'
    : `<div class="np"><i></i>Flat grey tile: not proven, could be normal year to year variation</div>
    <div class="note">Raised columns are proven changes; taller means a bigger change.</div>`;
  return `<div class="note">${esc(variable.name)}: change per decade (${esc(variable.unit)})</div>
    <div class="bar" style="background:linear-gradient(90deg,${pal[0]},${pal[1]},${pal[2]})"></div>
    <div class="scale"><span>-${r}</span><span>0</span><span>+${r}</span></div>
    ${notes}`;
}

function shell(panel, inner) {
  panel.hidden = false;
  panel.innerHTML = `<button class="btn close" aria-label="Close panel">×</button>${inner}`;
  panel.querySelector('.close').onclick = () => { panel.hidden = true; };
}

export function showLoading(panel, title) {
  shell(panel, `<h2>${esc(title)}</h2><div class="loading">Asking NASA data…</div>`);
}

export function showMessage(panel, title, message, kind = 'info') {
  shell(panel, `<h2>${esc(title)}</h2><div class="callout ${kind}">${esc(message)}</div>`);
}

export function showTrend(panel, res, placeLabel) {
  const v = res.variable, t = res.trend;
  const where = placeLabel || res.location.name || `${res.location.lat.toFixed(2)}, ${res.location.lon.toFixed(2)}`;
  const used = res.series.filter((s) => s.value !== null).length;
  shell(panel, `
    <h2>${esc(v.name)}</h2>
    <div class="where">${esc(where)} · ${res.period.start} to ${res.period.end}</div>
    ${res.mock ? `<div class="callout warn">${esc(res.mock_note || 'Sample data.')}</div>` : ''}
    <span class="badge ${t.confidence}">${LEVEL_TEXT[t.confidence]}</span>
    <div class="rate">${fmt(t.slope_per_decade)} ${esc(v.unit)} per decade</div>
    ${t.ci_low !== null && t.ci_high !== null ? `<p class="range">Likely between ${fmt(t.ci_low)} and ${fmt(t.ci_high)} per decade (95% range)</p>` : ''}
    <div class="chart" id="trend-chart"></div>
    <p class="sentence">${esc(res.sentence)}</p>
    ${res.caution ? `<div class="callout warn">${esc(res.caution)}</div>` : ''}
    <div class="callout info"><strong>What is this?</strong> ${esc(v.definition)}</div>
    <details>
      <summary>How we know</summary>
      <dl>
        <dt>p-value</dt><dd>${t.p < 0.001 ? '< 0.001' : t.p.toFixed(3)}</dd>
        <dt>q-value</dt><dd>${t.q === null ? 'not used for a single place' : t.q.toFixed(3)}</dd>
        <dt>Years used</dt><dd>${used} of ${res.series.length}</dd>
        <dt>Change starts</dt><dd>${t.change_start_year ?? 'not detected'}</dd>
        <dt>Method</dt><dd>${esc(t.method)}</dd>
        <dt>Data</dt><dd>${esc(v.source)}</dd>
      </dl>
      <p>The p-value is the chance of seeing a trend this strong if nothing were really changing. It is not the chance that the trend is true.</p>
    </details>`);
  drawChart(document.getElementById('trend-chart'), res);
}

export function showCellSummary(panel, props, variable, label, reason) {
  shell(panel, `
    <h2>${esc(variable.name)}</h2>
    <div class="where">${esc(label)}</div>
    <span class="badge ${props.confidence}">${LEVEL_TEXT[props.confidence]}</span>
    <div class="rate">${fmt(Number(props.slope))} ${esc(variable.unit)} per decade</div>
    <p class="range">q-value ${props.q === null || props.q === undefined ? 'n/a' : Number(props.q).toFixed(3)} (corrected for testing many cells at once)</p>
    <div class="callout info">${esc(reason)}</div>`);
}

function drawChart(el, res) {
  const s = res.series.filter((p) => p.value !== null);
  const t = res.trend;
  const lineColor = t.confidence === 'not_proven' ? '#9aa3ae' : '#ffcc66';
  Plotly.newPlot(el, [
    { x: s.map((p) => p.year), y: s.map((p) => p.value), mode: 'lines+markers', name: 'Yearly average',
      line: { color: '#6fd3ff', width: 2 }, marker: { size: 5 }, hovertemplate: '%{x}: %{y:.2f}<extra></extra>' },
    { x: t.line.map((p) => p.year), y: t.line.map((p) => p.value), mode: 'lines', name: 'Trend',
      line: { color: lineColor, width: 2.5, dash: 'dash' }, hoverinfo: 'skip' },
  ], {
    margin: { l: 44, r: 8, t: 6, b: 28 }, height: 220,
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#9aabc2', size: 11 },
    xaxis: { gridcolor: 'rgba(255,255,255,0.06)', zeroline: false },
    yaxis: { gridcolor: 'rgba(255,255,255,0.08)', zeroline: false, title: { text: res.variable.unit, standoff: 6 } },
    showlegend: false,
  }, { displayModeBar: false, responsive: true });
}
