// CropShift Earth: wires the globe, search, the Trends tab and the farming tabs together.
import { api, loadStatic } from './api.js';
import { Globe } from './globe.js';
import { setupSearch } from './search.js';
import { describePlace } from './geo.js';
import { gridToGeoJSON, legendHTML, showCellSummary, showLoading, showMessage, showTrend, varInfo, worldImage } from './trends.js';
import { buildFarmCells, cellPanelHTML, cropMap, decisionLists, landMap } from './farming.js';
import { methodsHTML } from './methods.js';

const $ = (id) => document.getElementById(id);
// Most detailed border per country: Egypt has its own 1:10m file, the rest use 1:50m.
const DETAILED_BORDER = { EGY: 'data/regions/EGY.geojson' };
const EGYPT = { iso: 'EGY', label: 'Egypt', bbox: [24.7, 22, 36.866, 31.586] };

const state = {
  tab: 'trends',
  mock: false, // true when the API serves fixed samples (python run.py mock)
  variables: [],
  countries: null,
  places: null,
  borders50: null,
  borders: {},
  varCode: 'T2M',
  selection: null, // {kind: 'point'|'city'|'country', lat, lon, label, coords, iso, bbox}
  mapCountry: EGYPT, // the country the "Show trend map" button uses
  regionShown: null, // iso of the trend map on screen
  regionToken: 0, // ignore answers to outdated requests
  farm: { outlook: null, cells: null, crop: 'wheat', mode: 'irrigated', h: 0, cropView: 'score', landView: 'count', k: null, fromList: false },
};

const panel = $('panel');
let toastTimer = null;
function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 4500);
}

const currentVar = () => varInfo(state.variables.find((v) => v.code === state.varCode) || state.varCode);
const isFarmTab = () => state.tab !== 'trends';

function coordText(lat, lon) {
  return `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(2)}° ${lon >= 0 ? 'E' : 'W'}`;
}
function placeName(lat, lon, fallbackCountry = null) {
  if (!state.countries || !state.places) return coordText(lat, lon);
  return describePlace(lat, lon, state.countries, state.places, fallbackCountry);
}
// Farming cells all belong to Egypt, even when a coastal cell's center sits over the sea.
const farmPlace = (lat, lon) => placeName(lat, lon, 'Egypt').replace(/^Over water, /, 'Egypt (coast), ');

const globe = new Globe('globe', {
  onPoint: (ll) => (isFarmTab()
    ? openFarmPoint(ll.lat, ll.lng)
    : select({ kind: 'point', lat: ll.lat, lon: ll.lng, label: placeName(ll.lat, ll.lng), coords: coordText(ll.lat, ll.lng) })),
  onCell: (props) => (isFarmTab() ? openFarmCell(Number(props.k)) : openCell(props)),
});

/* ====================== Trends tab ====================== */

async function loadPointTrend() {
  const s = state.selection;
  if (!s || s.kind === 'country' || isFarmTab()) return;
  const v = currentVar();
  showLoading(panel, `${v.name} at ${s.label}`);
  try {
    const res = await api.point(s.lat, s.lon, v.code);
    const where = `${s.label} · ${s.coords}`;
    showTrend(panel, res, where, state.mock ? 'Sample mode: the server is running on fixed sample data (Cairo). Start it with python run.py api for real data.' : null);
  } catch (e) {
    showMessage(panel, `${v.name} at ${s.label}`, e.message, 'warn');
  }
}

async function openCell(props) {
  const v = currentVar();
  const lat = Number(props.lat), lon = Number(props.lon);
  const label = `Grid cell, ${placeName(lat, lon)} · ${coordText(lat, lon)}`;
  showLoading(panel, `${v.name}, grid cell`);
  try {
    const res = await api.cell(lat, lon, v.code);
    showTrend(panel, res, label, state.mock ? 'Sample mode: fixed sample data (Cairo).' : null);
  } catch (e) {
    showCellSummary(panel, props, v, label, `${e.message} The numbers above come from the map.`);
  }
}

function select(sel) {
  if (isFarmTab()) setTab('trends');
  state.selection = sel;
  const kindText = { point: 'Point', city: 'City (30 km around the center)', country: 'Country' }[sel.kind];
  $('selection-text').textContent = `${sel.label}${sel.coords ? ` (${sel.coords})` : ''} · ${kindText}`;
  if (sel.kind === 'point') globe.selectPoint(sel.lon, sel.lat);
  if (sel.kind === 'city') globe.selectCity(sel.lon, sel.lat);
  if (sel.kind === 'country') {
    state.mapCountry = { iso: sel.iso, label: sel.label, bbox: sel.bbox };
    globe.selectCountry(sel.iso, sel.bbox);
    showRegion(state.mapCountry);
    return;
  }
  loadPointTrend();
}

async function borderOf(iso) {
  if (!(iso in state.borders)) {
    if (DETAILED_BORDER[iso]) {
      state.borders[iso] = (await loadStatic(DETAILED_BORDER[iso])).geometry;
    } else {
      state.borders50 = state.borders50 || await loadStatic('data/borders_50m.geojson');
      const f = state.borders50.features.find((x) => x.properties.iso === iso);
      state.borders[iso] = f ? f.geometry : null;
    }
  }
  return state.borders[iso];
}

function setRegionButton() {
  const btn = $('region-toggle');
  const on = state.regionShown === state.mapCountry.iso;
  btn.textContent = on ? `Hide trend map: ${state.mapCountry.label}` : `Show trend map: ${state.mapCountry.label}`;
  btn.classList.toggle('on', on);
}

async function showRegion(country) {
  const v = currentVar();
  const token = ++state.regionToken;
  $('region-note').textContent = `Fetching NASA data for ${country.label}… The first time can take up to a minute.`;
  showMessage(panel, `${v.name} in ${country.label}`, 'Fetching NASA data for this country and testing every grid cell. '
    + 'The first time can take up to a minute; after that it is instant.');
  try {
    const [grid, border] = await Promise.all([api.region(country.bbox, v.code), borderOf(country.iso)]);
    if (token !== state.regionToken || isFarmTab()) return;
    const { fc, range, counts } = gridToGeoJSON(grid, border);
    globe.showCells(fc, border);
    state.regionShown = country.iso;
    setRegionButton();
    $('region-note').textContent = `Inside ${country.label}: ${counts.increasing} cells rising, ${counts.decreasing} falling, `
      + `${counts.not_proven} not proven (of ${counts.total}). Each cell is about 55 by 60 km.`;
    $('legend').innerHTML = legendHTML(v, range, 'region');
    $('legend').hidden = false;
    showMessage(panel, `${v.name} in ${country.label}`, (state.mock ? 'Sample mode: the map shows the fixed Egypt sample. ' : '')
      + (grid.mean_sentence ? `${grid.mean_sentence} ` : '') + 'Click a column, or any point, to see its trend.');
  } catch (e) {
    if (token !== state.regionToken) return;
    hideRegion();
    $('region-note').textContent = e.message;
    showMessage(panel, `${v.name} in ${country.label}`, e.message, 'warn');
  }
}

function hideRegion() {
  globe.hideCells();
  state.regionShown = null;
  setRegionButton();
  $('region-note').textContent = '';
  if (!$('world-toggle').checked) $('legend').hidden = true;
}

let worldLegend = null;
async function loadWorld() {
  const v = currentVar();
  if (!$('world-toggle').checked || isFarmTab()) { globe.hideWorld(); if (!$('world-toggle').checked) $('world-note').textContent = ''; return; }
  $('world-note').textContent = 'Loading the world map…';
  try {
    const g = await api.world(v.code);
    if (isFarmTab()) return;
    const img = worldImage(g);
    globe.showWorld(img);
    const s = g.summary;
    $('world-note').textContent = `Whole Earth: ${s.increasing.toLocaleString()} cells proven rising, `
      + `${s.decreasing.toLocaleString()} proven falling, ${s.not_proven.toLocaleString()} not proven (of ${s.cells.toLocaleString()}).`;
    worldLegend = legendHTML(v, img.range, 'world');
    if (!state.regionShown) { $('legend').innerHTML = worldLegend; $('legend').hidden = false; }
  } catch (e) {
    globe.hideWorld();
    $('world-note').textContent = e.message;
  }
}

/* ====================== Farming tabs ====================== */

async function ensureFarm() {
  const f = state.farm;
  if (f.outlook) return true;
  $('farm-note').textContent = 'Loading the farming outlook for Egypt…';
  try {
    const [o, border] = await Promise.all([api.farming('EGY'), borderOf('EGY')]);
    f.outlook = o;
    f.cells = buildFarmCells(o, border);
    f.border = border;
    const sel = $('crop-select');
    sel.innerHTML = o.crops.map((c) => `<option value="${c.id}">${c.name}</option>`).join('');
    sel.value = f.crop;
    $('farm-note').textContent = `${f.cells.length} grid cells of about 55 by 60 km cover Egypt. Click one to see every crop.`;
    return true;
  } catch (e) {
    $('farm-note').textContent = e.message;
    return false;
  }
}

function cropInfo() {
  const f = state.farm;
  const c = f.outlook.crops.find((x) => x.id === f.crop);
  if (!c) return '';
  const season = c.season_months >= 12 ? 'a tree: it must survive all 12 months' : `growing season of about ${c.season_months} months`;
  return `${c.name} (${c.scientific_name}): grows best at ${c.temp_opt_c[0]} to ${c.temp_opt_c[1]} °C, survives ${c.temp_abs_c[0]} to ${c.temp_abs_c[1]} °C; ${season}. Source: FAO ECOCROP.`;
}

function renderFarm() {
  const f = state.farm;
  if (!f.outlook) return;
  const o = f.outlook;
  let res;
  if (state.tab === 'crops') {
    $('crop-info').textContent = cropInfo();
    res = cropMap(o, f.cells, f.crop, f.mode, f.h, f.cropView);
  } else {
    res = landMap(o, f.cells, state.tab === 'decisions' ? 'irrigated' : f.mode, f.h, state.tab === 'decisions' ? 'change' : f.landView);
  }
  globe.showCells(res.map, f.border);
  $('legend').innerHTML = res.legend;
  $('legend').hidden = false;
  // The horizon buttons do not apply to views that already compare two dates.
  const fixed = (state.tab === 'crops' && f.cropView === 'heat') || (state.tab === 'farmland' && f.landView === 'change');
  document.querySelectorAll('#horizon-seg button').forEach((b) => { b.disabled = fixed; });
  $('horizon-label').textContent = fixed ? 'When (fixed for this view)' : 'When';
  if (state.tab === 'decisions' && !f.fromList) showDecisions();
  else if (f.k !== null) openFarmCell(f.k, f.fromList);
  else showMessage(panel, state.tab === 'crops' ? `Where can ${o.crops.find((c) => c.id === f.crop).name.toLowerCase()} grow?` : 'Farming potential in Egypt',
    'Click any cell on the map to see every crop for that place: now, in 2035, and how many years before the heat becomes too much.');
}

function showDecisions() {
  const f = state.farm;
  f.fromList = false;
  panel.hidden = false;
  panel.innerHTML = `<button class="btn close" aria-label="Close panel">×</button>${decisionLists(f.outlook, f.cells, farmPlace)}`;
  panel.querySelector('.close').onclick = () => { panel.hidden = true; };
  panel.querySelectorAll('.rank li').forEach((li) => {
    const go = () => {
      if (li.dataset.crop) state.farm.crop = li.dataset.crop;
      globe.flyToCell(Number(li.dataset.lon), Number(li.dataset.lat));
      openFarmCell(Number(li.dataset.k), true);
    };
    li.onclick = go;
    li.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } };
  });
}

function openFarmCell(k, fromList = false) {
  const f = state.farm;
  if (!f.outlook) return;
  f.k = k;
  f.fromList = fromList;
  const cell = f.cells.find((c) => c.k === k);
  if (!cell) return;
  const label = `${farmPlace(cell.lat, cell.lon)} · ${coordText(cell.lat, cell.lon)}`;
  const mode = state.tab === 'decisions' ? 'irrigated' : f.mode;
  panel.hidden = false;
  panel.innerHTML = `<button class="btn close" aria-label="Close panel">×</button>
    ${fromList ? '<button class="btn" id="back-to-list" style="margin-bottom:8px">← Back to the list</button>' : ''}
    ${cellPanelHTML(f.outlook, k, mode, label, f.crop)}`;
  panel.querySelector('.close').onclick = () => { panel.hidden = true; f.k = null; };
  const back = $('back-to-list');
  if (back) back.onclick = () => { f.k = null; showDecisions(); };
  globe.pin(cell.lon, cell.lat);
}

function openFarmPoint(lat, lon) {
  const f = state.farm;
  if (!f.outlook) return;
  const { lat0, lon0, dlat, dlon, ncols } = f.outlook.grid;
  const k = Math.round((lat - lat0) / dlat) * ncols + Math.round((lon - lon0) / dlon);
  if (f.cells.some((c) => c.k === k)) openFarmCell(k);
  else showMessage(panel, placeName(lat, lon), 'Farming analysis is available for Egypt. Click a place inside Egypt, or use the Trends tab here.');
}

/* ====================== How we know ====================== */

async function showMethods() {
  showLoading(panel, 'How we know');
  try {
    const v = await api.validation();
    panel.hidden = false;
    panel.innerHTML = `<button class="btn close" aria-label="Close panel">×</button>${methodsHTML(v)}`;
    panel.querySelector('.close').onclick = () => { panel.hidden = true; };
    panel.scrollTop = 0;
  } catch (e) {
    showMessage(panel, 'How we know', e.message, 'warn');
  }
}

/* ====================== tabs ====================== */

async function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.tabs [role="tab"]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
  document.querySelectorAll('[data-for]').forEach((el) => { el.hidden = !el.dataset.for.split(' ').includes(tab); });
  if (tab === 'trends') {
    globe.hideCells();
    $('legend').hidden = true;
    loadWorld();
    if (state.regionShown) showRegion(state.mapCountry);
    else if (state.selection && state.selection.kind !== 'country') loadPointTrend();
    else panel.hidden = true;
    return;
  }
  globe.hideWorld();
  state.farm.fromList = false;
  if (!(await ensureFarm())) return;
  globe.selectCountry('EGY', EGYPT.bbox);
  renderFarm();
}

function bindSeg(selector, apply) {
  document.querySelectorAll(selector).forEach((b) => {
    b.onclick = () => {
      b.parentElement.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
      apply(b);
      renderFarm();
    };
  });
}

/* ====================== setup ====================== */

function fillVariables() {
  const sel = $('var-select');
  sel.innerHTML = '';
  for (const v of state.variables) {
    const o = document.createElement('option');
    const info = varInfo(v);
    o.value = v.code;
    o.textContent = `${info.name} (${info.unit})`;
    sel.appendChild(o);
  }
  sel.value = state.varCode;
  $('var-definition').textContent = currentVar()?.definition || '';
  sel.onchange = () => {
    state.varCode = sel.value;
    $('var-definition').textContent = currentVar().definition;
    loadWorld();
    if (state.regionShown) showRegion(state.mapCountry);
    loadPointTrend();
  };
}

async function init() {
  try {
    const [health, vars, countries, places] = await Promise.all([
      api.health(), api.variables(), loadStatic('data/countries.geojson'), loadStatic('data/places.json'),
    ]);
    state.mock = Boolean(health.mock);
    state.variables = vars.variables;
    state.countries = countries;
    state.places = places;
    fillVariables();
    setupSearch({
      input: $('search-input'), list: $('search-list'), countries, places,
      onPick: (r) => (r.kind === 'country'
        ? select({ kind: 'country', iso: r.iso, bbox: r.bbox, label: r.name })
        : select({ kind: 'city', lat: r.lat, lon: r.lon, label: `${r.name}, ${r.country}`, coords: coordText(r.lat, r.lon) })),
    });
    loadWorld();
  } catch (e) {
    toast(`Could not reach the server: ${e.message}`);
  }
  setRegionButton();
  $('region-toggle').onclick = () => {
    if (state.regionShown === state.mapCountry.iso) return hideRegion();
    globe.selectCountry(state.mapCountry.iso, state.mapCountry.bbox);
    showRegion(state.mapCountry);
  };
  $('world-toggle').onchange = loadWorld;
  $('btn-methods').onclick = showMethods;
  $('btn-home').onclick = () => globe.home();
  $('btn-proj').onclick = () => { $('btn-proj').textContent = globe.toggleProjection() ? 'Switch to 2D' : 'Switch to 3D'; };

  document.querySelectorAll('.tabs [role="tab"]').forEach((b) => { b.onclick = () => setTab(b.dataset.tab); });
  $('crop-select').onchange = (e) => { state.farm.crop = e.target.value; renderFarm(); };
  bindSeg('[data-crop-view]', (b) => { state.farm.cropView = b.dataset.cropView; });
  bindSeg('[data-land-view]', (b) => { state.farm.landView = b.dataset.landView; });
  bindSeg('[data-mode]', (b) => { state.farm.mode = b.dataset.mode; });
  bindSeg('[data-h]', (b) => { state.farm.h = Number(b.dataset.h); });
}

init();
window.__cropshift = { globe, state }; // handy for debugging in the browser console
