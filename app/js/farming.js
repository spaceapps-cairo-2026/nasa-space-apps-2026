// Crops, Farmland and Decisions tabs (F2, F3, F4): colors, panel and ranked lists from a FarmingOutlook.
// The outlook can come from the FAO calculator or from a trained model (contracts/farming.schema.json).
// Only the suitability scores are required; every other field is used when present and skipped when not.
import { borderTouchIndex, cutCell } from './geo.js';

const GREEN = ['#f3efc2', '#c2e186', '#5fb85b', '#1a7f3c', '#0b5a2a'];
const CHANGE = ['#a6611a', '#dfc27d', '#f2f2f2', '#80cdc1', '#018571'];
const CANNOT = '#5b4a3b';
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const EV_TEXT = { S: 'strong evidence', M: 'moderate evidence', N: 'not proven', '-': 'no data' };

function hex(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function ramp(stops, t) {
  t = Math.max(0, Math.min(1, t));
  const x = t * (stops.length - 1), i = Math.min(stops.length - 2, Math.floor(x)), f = x - i;
  const a = hex(stops[i]), b = hex(stops[i + 1]);
  return '#' + a.map((v, n) => Math.round(v + (b[n] - v) * f).toString(16).padStart(2, '0')).join('');
}
function esc(s) { const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }
const sign = (x, d = 1) => (x > 0 ? '+' : '') + x.toFixed(d);
const gradient = (stops) => `linear-gradient(90deg,${stops.join(',')})`;

/** Cut every grid cell of the outlook to the country border once; reused by every view. */
export function buildFarmCells(o, border) {
  const { lat0, lon0, dlat, dlon, nrows, ncols } = o.grid;
  const touched = borderTouchIndex(border, lat0, lon0, dlat, dlon);
  const gap = Math.min(0.025, dlon * 0.04);
  const cells = [];
  for (let i = 0; i < nrows; i++) {
    for (let j = 0; j < ncols; j++) {
      const k = i * ncols + j;
      if (o.inside[k] !== '1') continue;
      const lat = lat0 + i * dlat, lon = lon0 + j * dlon;
      const full = [lon - dlon / 2, lat - dlat / 2, lon + dlon / 2, lat + dlat / 2];
      const geometry = cutCell(full, [full[0] + gap, full[1] + gap, full[2] - gap, full[3] - gap], border, touched, `${i},${j}`);
      if (geometry) cells.push({ k, lat, lon, geometry });
    }
  }
  return cells;
}

const score = (o, mode, crop, h, k) => o.suitability?.[mode]?.[crop]?.[h]?.[k] ?? 0;
const threshold = (o) => o.suitable_threshold ?? 50;
const fits = (o, mode, h, k) => o.crops.filter((c) => score(o, mode, c.id, h, k) >= threshold(o)).length;
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const modeText = (mode) => (mode === 'irrigated' ? 'irrigated' : 'rain only');

/** Does the outlook have scores for this water mode ("irrigated" or "rainfed")? */
export const hasMode = (o, mode) => Boolean(o.suitability?.[mode] && Object.keys(o.suitability[mode]).length);
/** Does the outlook say how many years each crop has before its heat limit? */
export const hasHeat = (o) => Object.values(o.years_to_heat_limit || {}).some((g) => Array.isArray(g) && g.some(isNum));
/** One line about a crop for the sidebar, built only from the fields the outlook has. */
export function cropInfoText(o, cropId) {
  const c = o.crops.find((x) => x.id === cropId);
  if (!c) return '';
  const parts = [];
  if (Array.isArray(c.temp_opt_c)) parts.push(`grows best at ${c.temp_opt_c[0]} to ${c.temp_opt_c[1]} °C`);
  if (Array.isArray(c.temp_abs_c)) parts.push(`survives ${c.temp_abs_c[0]} to ${c.temp_abs_c[1]} °C`);
  let text = `${c.name}${c.scientific_name ? ` (${c.scientific_name})` : ''}${parts.length ? `: ${parts.join(', ')}` : ''}`;
  if (isNum(c.season_months)) text += `; ${c.season_months >= 12 ? 'a tree: it must survive all 12 months' : `growing season of about ${c.season_months} months`}`;
  return `${text}.${o.source ? ` Source: ${o.source}.` : ''}`;
}
const meanChange = (o, mode, k) => {
  const last = o.horizons.length - 1;
  return o.crops.reduce((t, c) => t + score(o, mode, c.id, last, k) - score(o, mode, c.id, 0, k), 0) / o.crops.length;
};

function fc(cells, props) {
  return {
    type: 'FeatureCollection',
    features: cells.map((c) => ({ type: 'Feature', geometry: c.geometry, properties: { k: c.k, lat: c.lat, lon: c.lon, ...props(c) } })),
  };
}

/** Crops tab map: suitability of one crop, or years until its heat limit. */
export function cropMap(o, cells, crop, mode, h, view) {
  if (view === 'heat') {
    const yrs = o.years_to_heat_limit?.[crop] || [];
    const map = fc(cells, (c) => {
      const y = yrs[c.k];
      if (y === null || y === undefined) return { flat: true, color: '#7d838c', opacity: 0.3, height: 0 };
      const color = y <= 15 ? '#d7301f' : y <= 40 ? '#fc8d59' : y < 99 ? '#fee08b' : '#7fc97f';
      return { flat: false, color, height: 4000 + 46000 * (1 - Math.min(y, 99) / 99), years: y };
    });
    const legend = `<div class="note">Years until the hottest month of the best season reaches the crop's heat limit, if this place keeps warming at its measured rate</div>
      <div class="scale" style="gap:6px;flex-wrap:wrap;margin-top:6px">
        <span><i class="sw" style="background:#d7301f"></i>15 or less</span><span><i class="sw" style="background:#fc8d59"></i>16 to 40</span>
        <span><i class="sw" style="background:#fee08b"></i>41 to 98</span><span><i class="sw" style="background:#7fc97f"></i>safe for 99+</span></div>
      <div class="note">Taller = sooner. Grey = cannot grow here now, or not warming.</div>`;
    return { map, legend };
  }
  const map = fc(cells, (c) => {
    const s = score(o, mode, crop, h, c.k);
    // Flat colored tiles: a clean map where the land shows through (columns are kept for urgency views).
    return s <= 0 ? { flat: true, color: CANNOT, opacity: 0.6, height: 0, score: 0 }
      : { flat: true, color: ramp(GREEN, s / 100), opacity: 0.78, height: 0, score: s };
  });
  const legend = `<div class="note">Suitability, 0 to 100 (${modeText(mode)}, ${o.horizons[h]})</div>
    <div class="bar" style="background:${gradient(GREEN)}"></div>
    <div class="scale"><span>1</span><span>50</span><span>100</span></div>
    <div class="np"><i style="background:${CANNOT}"></i>Brown: score 0, a climate unlike the places that grow it${mode === 'rainfed' ? ' (or under 100 mm of rain a year)' : ''}</div>`;
  return { map, legend };
}

/** Farmland tab map: how many crops fit, or how farming potential changes by the last horizon. */
export function landMap(o, cells, mode, h, view) {
  const n = o.crops.length;
  if (view === 'change') {
    const vals = cells.map((c) => meanChange(o, mode, c.k));
    const sorted = vals.map(Math.abs).sort((a, b) => a - b);
    const range = Math.max(sorted[Math.floor(0.95 * (sorted.length - 1))] || 0, 0.5);
    const map = fc(cells, (c) => {
      const d = meanChange(o, mode, c.k);
      if (Math.abs(d) < 0.25) return { flat: true, color: '#9aa3ae', opacity: 0.3, height: 0, change: d };
      return { flat: false, color: ramp(CHANGE, 0.5 + 0.5 * Math.max(-1, Math.min(1, d / range))), height: 3000 + 40000 * Math.min(1, Math.abs(d) / range), change: d };
    });
    const legend = `<div class="note">Average change of all ${n} crop scores from ${o.horizons[0]} to ${o.horizons[o.horizons.length - 1]}, points (${modeText(mode)})</div>
      <div class="bar" style="background:${gradient(CHANGE)}"></div>
      <div class="scale"><span>losing ${range.toFixed(1)}</span><span>0</span><span>gaining ${range.toFixed(1)}</span></div>
      <div class="np"><i></i>Flat grey: change under 0.25 points (too small to show)</div>`;
    return { map, legend };
  }
  const map = fc(cells, (c) => {
    const f = fits(o, mode, h, c.k);
    return f === 0 ? { flat: true, color: CANNOT, opacity: 0.6, height: 0, fits: 0 }
      : { flat: true, color: ramp(GREEN, f / n), opacity: 0.78, height: 0, fits: f };
  });
  const legend = `<div class="note">Number of the ${n} crops that fit (score ${threshold(o)} or more), ${o.horizons[h]}, ${modeText(mode)}</div>
    <div class="bar" style="background:${gradient(GREEN)}"></div>
    <div class="scale"><span>1</span><span>${Math.round(n / 2)}</span><span>${n}</span></div>
    <div class="np"><i style="background:${CANNOT}"></i>Brown: no crop fits</div>`;
  return { map, legend };
}

/** Right panel for one grid cell: climate, then every crop ranked, now vs the last horizon. */
export function cellPanelHTML(o, k, mode, placeLabel, selectedCrop) {
  const last = o.horizons.length - 1;
  const ev = o.evidence?.[k];
  const evBadge = ev && EV_TEXT[ev] ? ` <span class="ev ${ev}">${EV_TEXT[ev]}</span>` : '';
  const showHeat = hasHeat(o);
  const rows = o.crops.map((c) => {
    const now = score(o, mode, c.id, 0, k), later = score(o, mode, c.id, last, k);
    const lo = o.suitability_10_low?.[mode]?.[c.id]?.[k], hi = o.suitability_10_high?.[mode]?.[c.id]?.[k];
    return { c, now, later, d: later - now, lo, hi, heat: o.years_to_heat_limit?.[c.id]?.[k], m: o.best_start_month?.[mode]?.[c.id]?.[k] };
  }).sort((a, b) => b.now - a.now || b.later - a.later);
  const body = rows.map((r) => {
    const cls = r.d > 0 ? 'delta-up' : r.d < 0 ? 'delta-down' : 'delta-flat';
    const range = r.lo !== undefined && r.hi !== undefined && r.lo !== r.hi ? ` title="95% range ${r.lo} to ${r.hi}"` : '';
    const season = r.now > 0 && isNum(r.m) && isNum(r.c.season_months)
      ? (r.c.season_months >= 12 ? 'all year' : `${MON[r.m]} to ${MON[(r.m + r.c.season_months - 1) % 12]}`) : '';
    const heat = r.heat === null || r.heat === undefined ? '' : r.heat >= 99 ? '99+ y' : `${Math.round(r.heat)} y`;
    return `<tr class="${r.c.id === selectedCrop ? 'sel' : ''}">
      <td>${esc(r.c.name)}<span class="sub" style="display:block;color:var(--muted);font-size:11px">${season}</span></td>
      <td><div class="bar"><i style="width:${r.now}%;background:${r.now ? ramp(GREEN, r.now / 100) : 'transparent'}"></i></div></td>
      <td>${r.now}</td>${last > 0 ? `<td${range}>${r.later}</td><td class="${cls}">${r.d ? sign(r.d, 0) : '0'}</td>` : ''}${showHeat ? `<td>${heat}</td>` : ''}</tr>`;
  }).join('');
  const fitsNow = fits(o, mode, 0, k), fitsLater = fits(o, mode, last, k);
  return `
    <h2>Farming outlook</h2>
    <div class="where">${esc(placeLabel)}</div>
    <dl class="climate">
      ${isNum(o.temp_now_c?.[k]) ? `<dt>Average temperature</dt><dd>${o.temp_now_c[k]} °C${o.climate_period ? ` (${esc(o.climate_period)})` : ''}</dd>` : ''}
      ${isNum(o.rain_now_mm?.[k]) ? `<dt>Rain per year</dt><dd>${o.rain_now_mm[k]} mm</dd>` : ''}
      ${isNum(o.temp_trend_per_decade?.[k]) ? `<dt>Warming trend</dt><dd>${sign(o.temp_trend_per_decade[k], 2)} °C per decade${evBadge}</dd>` : ''}
      <dt>Crops that fit</dt><dd>${fitsNow} now${last > 0 ? `, ${fitsLater} in ${o.horizons[last]}` : ''} (${modeText(mode)})</dd>
      ${o.farmland ? `<dt>Farmed today</dt><dd>${o.farmland[k] === '1' ? 'yes' : 'no farmland mapped'}</dd>` : ''}
    </dl>
    ${mode === 'irrigated' && o.farmland && o.farmland[k] !== '1' ? '<div class="callout info">No farmland is mapped here today. Irrigated scores show what this climate could grow if water were brought here; they do not show that water is available.</div>' : ''}
    ${o.outside_training?.[k] === '1' ? '<div class="callout warn">This climate is partly outside the climates the crop model learned from, so read these scores with care.</div>' : ''}
    ${ev === 'N' ? '<div class="callout warn">The warming trend here is not proven, so the changes to 2035 are only a possibility.</div>' : ''}
    ${mode === 'rainfed' && fitsNow === 0 && hasMode(o, 'irrigated') ? '<div class="callout info">Rain only: no crop fits here on rain alone. Switch to Irrigated to see what this climate could grow with water.</div>' : ''}
    <table class="crop-table">
      <thead><tr><th>Crop</th><th></th><th>Now</th>${last > 0 ? `<th>${o.horizons[last]}</th><th>Change</th>` : ''}${showHeat ? '<th>Heat limit</th>' : ''}</tr></thead>
      <tbody>${body}</tbody>
    </table>
    <details><summary>How we know</summary>
      <p>${esc(o.method)}</p>
      ${o.score_note ? `<p>${esc(o.score_note)}</p>` : ''}
    </details>`;
}

/** Decisions tab: ranked planning signals, every row tied to a place on the map. */
export function decisionLists(o, cells, nameOf) {
  const mode = hasMode(o, 'irrigated') ? 'irrigated' : 'rainfed';
  const heat = [];
  for (const c of cells) {
    for (const crop of o.crops) {
      const y = o.years_to_heat_limit?.[crop.id]?.[c.k];
      if (!isNum(y) || y >= 99 || score(o, mode, crop.id, 0, c.k) < threshold(o)) continue;
      heat.push({ c, crop, y });
    }
  }
  heat.sort((a, b) => a.y - b.y);
  const seen = new Set();
  const heatTop = heat.filter((r) => { const key = `${r.crop.id}`; if (seen.has(key)) return false; seen.add(key); return true; }).slice(0, 8);
  const changes = cells.map((c) => ({ c, d: meanChange(o, mode, c.k) }));
  const rising = changes.filter((r) => r.d > 0.25).sort((a, b) => b.d - a.d).slice(0, 8);
  const losing = changes.filter((r) => r.d < -0.25).sort((a, b) => a.d - b.d).slice(0, 8);
  const best = cells.map((c) => ({ c, n: fits(o, mode, 0, c.k) })).filter((r) => r.n > 0).sort((a, b) => b.n - a.n).slice(0, 8);
  const li = (r, label, value) => `<li tabindex="0" data-k="${r.c.k}" data-lat="${r.c.lat}" data-lon="${r.c.lon}"${r.crop ? ` data-crop="${r.crop.id}"` : ''}>
      <span>${label}<span class="sub">${esc(nameOf(r.c.lat, r.c.lon))}${EV_TEXT[o.evidence?.[r.c.k]] ? ` <span class="ev ${o.evidence[r.c.k]}">${EV_TEXT[o.evidence[r.c.k]]}</span>` : ''}</span></span>
      <span class="val">${value}</span></li>`;
  const empty = '<p class="note">None found with the current data.</p>';
  return `
    <h2>Planning signals</h2>
    <div class="where">${esc((o.region && o.region.name) || 'Egypt')}, ${modeText(mode)} farming${o.horizons.length > 1 ? ", if today's measured trends continue" : ''}. Signals for planning, not instructions.</div>
    ${hasHeat(o) ? `<h3>Crops nearest their heat limit</h3>
    <p class="note">Where a crop grows well today, but its hottest season month will reach the crop's survival limit soonest.</p>
    ${heatTop.length ? `<ol class="rank">${heatTop.map((r) => li(r, esc(r.crop.name), Math.round(r.y) <= 1 ? 'about 1 year' : `${Math.round(r.y)} years`)).join('')}</ol>` : empty}` : ''}
    ${o.horizons.length > 1 ? `<h3>Gaining farming potential by ${o.horizons[o.horizons.length - 1]}</h3>
    ${rising.length ? `<ol class="rank">${rising.map((r) => li(r, 'Average crop score', sign(r.d))).join('')}</ol>` : empty}
    <h3>Losing farming potential by ${o.horizons[o.horizons.length - 1]}</h3>
    ${losing.length ? `<ol class="rank">${losing.map((r) => li(r, 'Average crop score', sign(r.d))).join('')}</ol>` : empty}`
    : `<h3>Where the most crops fit today</h3>
    ${best.length ? `<ol class="rank">${best.map((r) => li(r, 'Crops that fit', `${r.n} of ${o.crops.length}`)).join('')}</ol>` : empty}
    <p class="note">This outlook covers one year, so there is no change over time to rank.</p>`}
    <p class="note">Click a row to fly there and see every crop.${o.evidence ? ' Badges show how strong the evidence for the warming trend is.' : ''}</p>`;
}
