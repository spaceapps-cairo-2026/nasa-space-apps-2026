// CropShift Earth: wires the globe, search and the Trends tab together.
import { api, loadStatic } from './api.js';
import { Globe } from './globe.js';
import { setupSearch } from './search.js';
import { describePlace } from './geo.js';
import { gridToGeoJSON, legendHTML, showCellSummary, showLoading, showMessage, showTrend, worldImage } from './trends.js';

const $ = (id) => document.getElementById(id);
// Most detailed border per country: Egypt has its own 1:10m file, the rest use 1:50m.
const DETAILED_BORDER = { EGY: 'data/regions/EGY.geojson' };
const EGYPT = { iso: 'EGY', label: 'Egypt', bbox: [24.7, 22, 36.866, 31.586] };

const state = {
  variables: [],
  countries: null,
  places: null,
  borders50: null,
  borders: {},
  varCode: 'T2M',
  selection: null, // {kind: 'point'|'city'|'country', lat, lon, label, coords, iso, bbox}
  mapCountry: EGYPT, // the country the "Show trend map" button uses
  regionShown: null, // iso of the country map on screen
  regionToken: 0, // ignore answers to outdated requests
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

const currentVar = () => state.variables.find((v) => v.code === state.varCode);

function coordText(lat, lon) {
  return `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(2)}° ${lon >= 0 ? 'E' : 'W'}`;
}
function placeName(lat, lon) {
  if (!state.countries || !state.places) return coordText(lat, lon);
  return describePlace(lat, lon, state.countries, state.places);
}

const globe = new Globe('globe', {
  onPoint: (ll) => select({ kind: 'point', lat: ll.lat, lon: ll.lng, label: placeName(ll.lat, ll.lng), coords: coordText(ll.lat, ll.lng) }),
  onCell: (props) => openCell(props),
});

/* ---------- single place ---------- */

async function loadPointTrend() {
  const s = state.selection;
  if (!s || s.kind === 'country') return;
  const v = currentVar();
  showLoading(panel, `${v.name} at ${s.label}`);
  try {
    const res = await api.point(s.lat, s.lon, v.code, s.label);
    const where = `${s.label} · ${s.coords}`;
    showTrend(panel, res, res.mock ? `${where} (sample shows Cairo)` : where);
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
    showTrend(panel, res, label);
  } catch (e) {
    showCellSummary(panel, props, v, label, `${e.message} The numbers above come from the map.`);
  }
}

/* ---------- selection ---------- */

function select(sel) {
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

/* ---------- country trend map ---------- */

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
    const [grid, border] = await Promise.all([api.region(country.bbox, v.code, country.label), borderOf(country.iso)]);
    if (token !== state.regionToken) return;
    const { fc, range, counts } = gridToGeoJSON(grid, border);
    globe.showCells(fc, border);
    state.regionShown = country.iso;
    setRegionButton();
    $('region-note').textContent = `Inside ${country.label}: ${counts.increasing} cells rising, ${counts.decreasing} falling, `
      + `${counts.not_proven} not proven (of ${counts.total}). Each cell is about 55 by 60 km.`;
    $('legend').innerHTML = legendHTML(v, range, 'region');
    $('legend').hidden = false;
    showMessage(panel, `${v.name} in ${country.label}`, grid.mock
      ? 'Sample data: the live engine is not connected yet. Click a column, or any point, to see its trend.'
      : 'Click a column, or any point, to see its trend.');
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

/* ---------- whole Earth layer ---------- */

async function loadWorld() {
  const v = currentVar();
  if (!$('world-toggle').checked) { globe.hideWorld(); $('world-note').textContent = ''; return; }
  $('world-note').textContent = 'Loading the world map…';
  try {
    const g = await api.world(v.code);
    const img = worldImage(g);
    globe.showWorld(img);
    const s = g.summary;
    $('world-note').textContent = `Whole Earth: ${s.n_increasing.toLocaleString()} cells proven rising, `
      + `${s.n_decreasing.toLocaleString()} proven falling, ${s.n_not_proven.toLocaleString()} not proven.`;
    if (!state.regionShown) { $('legend').innerHTML = legendHTML(v, img.range, 'world'); $('legend').hidden = false; }
  } catch (e) {
    globe.hideWorld();
    $('world-note').textContent = e.message;
  }
}

/* ---------- setup ---------- */

function fillVariables() {
  const sel = $('var-select');
  sel.innerHTML = '';
  for (const v of state.variables) {
    const o = document.createElement('option');
    o.value = v.code;
    o.textContent = `${v.name} (${v.unit})`;
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
    const [vars, countries, places] = await Promise.all([
      api.variables(), loadStatic('data/countries.geojson'), loadStatic('data/places.json'),
    ]);
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
  $('btn-home').onclick = () => globe.home();
  $('btn-proj').onclick = () => { $('btn-proj').textContent = globe.toggleProjection() ? 'Switch to 2D' : 'Switch to 3D'; };
}

init();
window.__cropshift = { globe, state }; // handy for debugging in the browser console
