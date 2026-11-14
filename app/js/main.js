// CropShift Earth: wires the globe, search, the Trends tab and the farming tabs together.
import { api, loadStatic } from './api.js';
import { Globe } from './globe.js';
import { setupSearch } from './search.js';
import { describePlace } from './geo.js';
import { gridToGeoJSON, legendHTML, periodOf, showCellSummary, showLoading, showRegionSummary, showMessage, showTrend, varInfo, worldImage } from './trends.js';
import { buildFarmCells, cellPanelHTML, cropInfoText, cropMap, decisionLists, hasHeat, hasMode, landMap } from './farming.js';
import { methodsHTML } from './methods.js';
import { createTour } from './tour.js';

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
  years: { min: 2001, max: 2025, minRange: 10, from: 2001, to: 2025 }, // the years the trend is measured over
  regionPeriod: null, // years of the trend map on screen
  selection: null, // {kind: 'point'|'city'|'country', lat, lon, label, coords, iso, bbox}
  mapCountry: EGYPT, // the country the "Show trend map" button uses
  regionShown: null, // iso of the trend map on screen
  regionWanted: false, // the user asked for a trend map: draw it again when the measurement changes
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
// What the server offers for the chosen measurement (flags from /api/variables). Unknown = assume yes.
const canDo = (what) => (state.variables.find((v) => v.code === state.varCode) || {})[what] !== false;
const worldNames = () => state.variables.filter((v) => v.world !== false).map((v) => varInfo(v).name.toLowerCase());
function listText(a) { return a.length < 2 ? a.join('') : `${a.slice(0, -1).join(', ')} and ${a[a.length - 1]}`; }
/** A grid cell is 0.5 x 0.625 degrees: about 56 km tall everywhere, narrower away from the equator. */
function cellSizeText(lat) {
  const w = 0.625 * 111.32 * Math.cos((Math.min(Math.abs(lat), 89) * Math.PI) / 180);
  return `about 56 by ${Math.max(1, Math.round(w))} km`;
}
const midLat = (bbox) => (bbox[1] + bbox[3]) / 2;
const isFarmTab = () => state.tab !== 'trends';
const wholeRecord = () => state.years.from === state.years.min && state.years.to === state.years.max;
/** Extra request parameters for the chosen years; none when the whole record is chosen. */
const yearParams = () => (wholeRecord() ? {} : { start_year: state.years.from, end_year: state.years.to });

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

let pointToken = 0; // ignore answers to outdated requests (the years or the measurement changed meanwhile)
async function loadPointTrend() {
  const s = state.selection;
  if (!s || s.kind === 'country' || isFarmTab()) return;
  const v = currentVar();
  const token = ++pointToken;
  showLoading(panel, `${v.name} at ${s.label}`);
  try {
    const res = await api.point(s.lat, s.lon, v.code, yearParams());
    if (token !== pointToken) return;
    const where = `${s.label} · ${s.coords}`;
    showTrend(panel, res, where, state.mock ? 'Sample mode: the server is running on fixed sample data (Cairo). Start it with python run.py api for real data.' : null);
  } catch (e) {
    if (token === pointToken) showMessage(panel, `${v.name} at ${s.label}`, e.message, 'warn');
  }
}

async function openCell(props) {
  const v = currentVar();
  const lat = Number(props.lat), lon = Number(props.lon);
  const label = `Grid cell, ${placeName(lat, lon)} · ${coordText(lat, lon)}`;
  showLoading(panel, `${v.name}, grid cell`);
  try {
    const res = await api.cell(lat, lon, v.code, yearParams());
    showTrend(panel, res, label, state.mock ? 'Sample mode: fixed sample data (Cairo).' : null);
  } catch (e) {
    showCellSummary(panel, props, v, label, `${e.message} The numbers above come from the map.`, state.regionPeriod);
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
    return showRegion(state.mapCountry);
  }
  return loadPointTrend();
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
  const can = canDo('region');
  btn.disabled = !can;
  btn.textContent = !can ? `No trend map for ${currentVar().name.toLowerCase()}`
    : on ? `Hide trend map: ${state.mapCountry.label}` : `Show trend map: ${state.mapCountry.label}`;
  btn.classList.toggle('on', on && can);
}

/** The chosen measurement has no trend map: say so calmly, keep the wish so the map returns later. */
function regionUnavailable(country) {
  const v = currentVar();
  state.regionToken += 1;
  globe.hideCells();
  state.regionShown = null;
  setRegionButton();
  if (!$('world-toggle').checked || !canDo('world')) $('legend').hidden = true;
  const text = `Trend maps are not available for ${v.name.toLowerCase()} yet. Click any place to see its trend there, or pick another measurement to see the map of ${country.label}.`;
  $('region-note').textContent = text;
  if (!state.selection || state.selection.kind === 'country') showMessage(panel, `${v.name} in ${country.label}`, text);
}

async function showRegion(country) {
  const v = currentVar();
  state.regionWanted = true;
  if (!canDo('region')) return regionUnavailable(country);
  const token = ++state.regionToken;
  $('region-note').textContent = `Fetching NASA data for ${country.label}… The first time can take up to a minute.`;
  showMessage(panel, `${v.name} in ${country.label}`, 'Fetching NASA data for this country and testing every grid cell. '
    + 'The first time can take up to a minute; after that it is instant.');
  try {
    const [grid, border] = await Promise.all([api.region(country.bbox, v.code, country.iso, yearParams()), borderOf(country.iso)]);
    if (token !== state.regionToken || isFarmTab()) return;
    const { fc, range, counts } = gridToGeoJSON(grid, border);
    state.lastCounts = counts;
    state.regionPeriod = periodOf(grid);
    globe.showCells(fc, border);
    state.regionShown = country.iso;
    setRegionButton();
    $('region-note').textContent = `Inside ${country.label}, ${state.regionPeriod.text}: ${counts.increasing} cells rising, ${counts.decreasing} falling, `
      + `${counts.not_proven} not proven (of ${counts.total}). Each cell is ${cellSizeText(midLat(country.bbox))}.`;
    $('legend').innerHTML = legendHTML(v, range, 'region', state.regionPeriod);
    $('legend').hidden = false;
    showRegionSummary(panel, grid, `${v.name} in ${country.label}`, state.mock ? 'Sample mode: the map shows the fixed Egypt sample. ' : '');
    return counts;
  } catch (e) {
    if (token !== state.regionToken) return;
    hideRegion(true); // keep the wish: another measurement may work for this country
    $('region-note').textContent = e.message;
    showMessage(panel, `${v.name} in ${country.label}`, e.message, 'warn');
  }
}

function hideRegion(keepWanted = false) {
  state.regionToken += 1; // cancel a country map that is still loading
  globe.hideCells();
  state.regionShown = null;
  if (!keepWanted) state.regionWanted = false;
  setRegionButton();
  $('region-note').textContent = '';
  if (!$('world-toggle').checked || !canDo('world')) $('legend').hidden = true;
}

let worldLegend = null;
let worldToken = 0;
async function loadWorld() {
  const v = currentVar();
  const token = ++worldToken;
  $('world-toggle').disabled = !canDo('world');
  if (!canDo('world')) {
    // No whole Earth grid for this measurement yet: explain instead of asking the server for an error.
    globe.hideWorld();
    worldLegend = null;
    if (!state.regionShown) $('legend').hidden = true;
    const have = worldNames();
    $('world-note').textContent = `The whole Earth view is ready for ${have.length ? listText(have) : 'no measurement'} only so far. `
      + `For ${v.name.toLowerCase()}, pick a country or click a place.`;
    return;
  }
  if (!$('world-toggle').checked || isFarmTab()) { globe.hideWorld(); if (!$('world-toggle').checked) $('world-note').textContent = ''; return; }
  $('world-note').textContent = 'Loading the world map…';
  try {
    const g = await api.world(v.code, 2, yearParams());
    if (isFarmTab() || token !== worldToken) return;
    const img = worldImage(g);
    globe.showWorld(img);
    const s = g.summary;
    $('world-note').textContent = `Whole Earth, ${periodOf(g).text}: ${s.increasing.toLocaleString()} cells proven rising, `
      + `${s.decreasing.toLocaleString()} proven falling, ${s.not_proven.toLocaleString()} not proven (of ${s.cells.toLocaleString()}).`;
    worldLegend = legendHTML(v, img.range, 'world', periodOf(g));
    if (!state.regionShown) { $('legend').innerHTML = worldLegend; $('legend').hidden = false; }
  } catch (e) {
    if (token !== worldToken) return;
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
    setupFarmControls(o);
    $('farm-note').textContent = `${f.cells.length} grid cells of ${cellSizeText(midLat(EGYPT.bbox))} cover Egypt. Click one to see every crop.`;
    return true;
  } catch (e) {
    $('farm-note').textContent = e.message;
    return false;
  }
}

/**
 * Fit the farming controls to the outlook file (FAO calculator or a trained model): the crop list,
 * one button per horizon, and only the views and water modes the file has data for.
 */
function setupFarmControls(o) {
  const f = state.farm;
  if (!o.crops.some((c) => c.id === f.crop)) f.crop = o.crops[0].id;
  const sel = $('crop-select');
  sel.innerHTML = '';
  for (const c of o.crops) {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    sel.appendChild(opt);
  }
  sel.value = f.crop;

  const last = o.horizons.length - 1;
  f.h = Math.min(f.h, last);
  $('horizon-seg').innerHTML = o.horizons.map((y, i) => `<button data-h="${i}" class="${i === f.h ? 'on' : ''}">${i === 0 ? 'Now' : y}</button>`).join('');
  bindSeg('#horizon-seg [data-h]', (b) => { f.h = Number(b.dataset.h); });

  if (!hasMode(o, f.mode)) f.mode = hasMode(o, 'irrigated') ? 'irrigated' : 'rainfed';
  document.querySelectorAll('[data-mode]').forEach((b) => {
    b.disabled = !hasMode(o, b.dataset.mode);
    b.title = b.disabled ? 'This outlook has no scores for this water mode.' : '';
    b.classList.toggle('on', b.dataset.mode === f.mode);
  });

  const heat = hasHeat(o);
  if (!heat) f.cropView = 'score';
  document.querySelectorAll('[data-crop-view]').forEach((b) => {
    if (b.dataset.cropView === 'heat') b.hidden = !heat;
    b.classList.toggle('on', b.dataset.cropView === f.cropView);
  });
  const change = document.querySelector('[data-land-view="change"]');
  change.hidden = last === 0;
  change.textContent = `Change by ${o.horizons[last]}`;
  if (last === 0) { f.landView = 'count'; document.querySelector('[data-land-view="count"]').classList.add('on'); }

  $('farm-intro').innerHTML = '';
  $('farm-intro').append('Farming analysis for ', Object.assign(document.createElement('strong'), { textContent: (o.region && o.region.name) || 'Egypt' }),
    `${o.source ? `, from ${o.source}` : ''}. ${last > 0 ? "Future views assume today's measured trends continue; they are not forecasts." : ''}`);
}

const cropInfo = () => cropInfoText(state.farm.outlook, state.farm.crop);
const cropName = () => (state.farm.outlook.crops.find((c) => c.id === state.farm.crop) || state.farm.outlook.crops[0]).name;

function renderFarm() {
  const f = state.farm;
  if (!f.outlook) return;
  const o = f.outlook;
  let res;
  if (state.tab === 'crops') {
    $('crop-info').textContent = cropInfo();
    res = cropMap(o, f.cells, f.crop, f.mode, f.h, f.cropView);
  } else {
    res = landMap(o, f.cells, state.tab === 'decisions' ? decisionMode() : f.mode, f.h,
      state.tab === 'decisions' ? (o.horizons.length > 1 ? 'change' : 'count') : f.landView);
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
  else showMessage(panel, state.tab === 'crops' ? `Where can ${cropName().toLowerCase()} grow?` : 'Farming potential in Egypt',
    `Click any cell on the map to see every crop for that place: now${o.horizons.length > 1 ? `, in ${o.horizons[o.horizons.length - 1]}` : ''}`
    + `${hasHeat(o) ? ', and how many years before the heat becomes too much' : ''}.`);
}

// The Decisions tab is about irrigated farming; an outlook with rain-fed scores only uses those.
const decisionMode = () => (hasMode(state.farm.outlook, 'irrigated') ? 'irrigated' : 'rainfed');

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
  const mode = state.tab === 'decisions' ? decisionMode() : f.mode;
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
    return v;
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
    setRegionButton();
    loadWorld();
    if (state.regionShown || state.regionWanted) showRegion(state.mapCountry);
    loadPointTrend();
  };
}

/** The year range picker: any range of at least minRange years inside the record. */
function fillYears() {
  const y = state.years;
  const from = $('year-from'), to = $('year-to');
  const options = (lo, hi) => { let h = ''; for (let k = lo; k <= hi; k++) h += `<option value="${k}">${k}</option>`; return h; };
  from.innerHTML = options(y.min, y.max - y.minRange + 1);
  to.innerHTML = options(y.min + y.minRange - 1, y.max);
  const show = () => {
    from.value = y.from; to.value = y.to;
    $('year-reset').hidden = wholeRecord();
    const n = y.to - y.from + 1;
    $('year-note').textContent = wholeRecord() ? `The whole NASA record, ${n} years. Pick any range of at least ${y.minRange} years.`
      : `${n} years chosen. Shorter ranges prove fewer changes: fewer years to tell a real change from normal ups and downs.`;
  };
  const reload = () => {
    show();
    loadWorld();
    if (state.regionShown || state.regionWanted) showRegion(state.mapCountry);
    loadPointTrend();
  };
  from.onchange = () => { y.from = Number(from.value); if (y.to - y.from + 1 < y.minRange) y.to = y.from + y.minRange - 1; reload(); };
  to.onchange = () => { y.to = Number(to.value); if (y.to - y.from + 1 < y.minRange) y.from = y.to - y.minRange + 1; reload(); };
  $('year-reset').onclick = () => { y.from = y.min; y.to = y.max; reload(); };
  state.resetYears = () => { if (!wholeRecord()) { y.from = y.min; y.to = y.max; show(); } };
  show();
}

async function init() {
  try {
    const [health, vars, countries, places] = await Promise.all([
      api.health(), api.variables(), loadStatic('data/countries.geojson'), loadStatic('data/places.json'),
    ]);
    state.mock = Boolean(health.mock);
    state.variables = vars.variables;
    if (vars.start_year && vars.end_year) {
      Object.assign(state.years, { min: vars.start_year, max: vars.end_year, from: vars.start_year, to: vars.end_year, minRange: vars.min_range_years || 10 });
    }
    fillYears();
    state.countries = countries;
    state.places = places;
    fillVariables();
    setRegionButton();
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
}

/* ====================== guided tour ====================== */

function countryByIso(iso) {
  const f = state.countries && state.countries.features.find((x) => x.properties.iso === iso);
  return f ? { iso, bbox: f.properties.bbox, label: f.properties.name } : null;
}

const tour = createTour({
  reset: async () => {
    if (state.resetYears) state.resetYears(); // the tour tells the whole record's story
    hideRegion();
    globe.clearSelection();
    state.selection = null;
    $('selection-text').textContent = 'None yet. Click anywhere on Earth or search a place.';
    panel.hidden = true;
  },
  home: () => globe.home(),
  closePanel: () => { panel.hidden = true; },
  setTab: (tab) => setTab(tab),
  selectCountry: async (iso) => {
    const c = countryByIso(iso);
    if (!c) return null;
    const counts = await select({ kind: 'country', ...c });
    return counts || null;
  },
  selectPoint: (lat, lon) => select({ kind: 'point', lat, lon, label: placeName(lat, lon), coords: coordText(lat, lon) }),
  setCrop: (crop, view) => {
    const o = state.farm.outlook;
    if (!o) return null;
    // A model's file may not have this crop or this view: fall back to what it does have.
    const wanted = (Array.isArray(crop) ? crop : [crop]).find((id) => o.crops.some((c) => c.id === id));
    state.farm.crop = wanted ?? o.crops[0].id;
    state.farm.cropView = view === 'heat' && !hasHeat(o) ? 'score' : view;
    $('crop-select').value = state.farm.crop;
    document.querySelectorAll('[data-crop-view]').forEach((b) => b.classList.toggle('on', b.dataset.cropView === state.farm.cropView));
    state.farm.k = null;
    renderFarm();
    return { id: state.farm.crop, name: cropName(), view: state.farm.cropView };
  },
  showMethods: () => showMethods(),
});
$('btn-tour').onclick = () => tour.start();

/* ====================== welcome ====================== */

function closeWelcome() {
  $('welcome').hidden = true;
  try { localStorage.setItem('cropshift-welcomed', '1'); } catch { /* private window: fine */ }
}
$('welcome-tour').onclick = () => { closeWelcome(); tour.start(); };
$('welcome-explore').onclick = closeWelcome;
$('welcome').addEventListener('click', (e) => { if (e.target.id === 'welcome') closeWelcome(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('welcome').hidden) closeWelcome(); });
let welcomed = false;
try { welcomed = localStorage.getItem('cropshift-welcomed') === '1'; } catch { /* show it */ }
// ?welcome in the address forces it (useful before a demo); ?nowelcome hides it (useful for recording).
const params = new URLSearchParams(window.location.search);
if (params.has('welcome') || (!welcomed && !params.has('nowelcome'))) $('welcome').hidden = false;

init();
window.__cropshift = { globe, state, tour }; // handy for debugging in the browser console
