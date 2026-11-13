// CropShift Earth: wires the globe, search and the Trends tab together.
import { api, loadStatic } from './api.js';
import { Globe } from './globe.js';
import { setupSearch } from './search.js';
import { describePlace } from './geo.js';
import { cellsToGeoJSON, legendHTML, showCellSummary, showLoading, showMessage, showTrend } from './trends.js';

const $ = (id) => document.getElementById(id);
// Region id -> country code, and the detailed border file used to clip its map.
const REGION_FOR_ISO = { EGY: 'egypt' };
const REGION_BORDER = { egypt: 'data/regions/EGY.geojson' };

const state = {
  variables: [],
  regions: [],
  countries: null,
  places: null,
  borders: {},
  varCode: 'T2M',
  selection: null, // {kind: 'point'|'city'|'country', lat, lon, label, iso}
  regionShown: null, // region id or null
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

function select(sel) {
  state.selection = sel;
  const kindText = { point: 'Point', city: 'City (30 km around the center)', country: 'Country' }[sel.kind];
  $('selection-text').textContent = `${sel.label}${sel.coords ? ` (${sel.coords})` : ''} · ${kindText}`;
  if (sel.kind === 'point') globe.selectPoint(sel.lon, sel.lat);
  if (sel.kind === 'city') globe.selectCity(sel.lon, sel.lat);
  if (sel.kind === 'country') {
    globe.selectCountry(sel.iso, sel.bbox);
    const region = REGION_FOR_ISO[sel.iso];
    if (region && state.regions.some((r) => r.id === region)) {
      showRegion(region);
      showMessage(panel, sel.label, 'Each column is one grid cell (about 55 km). Click a column, or click any point, to see its trend.');
    } else {
      const names = state.regions.map((r) => r.name.split(' (')[0]).join(', ') || 'none yet';
      showMessage(panel, sel.label, `Regional maps are available for: ${names}. Click any point inside ${sel.label} to see its trend.`);
    }
    return;
  }
  loadPointTrend();
}

async function showRegion(regionId) {
  const v = currentVar();
  const btn = $('region-toggle');
  try {
    const [region, border] = await Promise.all([api.region(regionId, v.code), loadBorder(regionId)]);
    const { fc, range, counts } = cellsToGeoJSON(region, border);
    globe.showCells(fc, border);
    state.regionShown = regionId;
    btn.textContent = 'Hide Egypt trend map';
    btn.classList.add('on');
    $('region-note').textContent = `Inside the border: ${counts.increasing} cells rising, ${counts.decreasing} falling, `
      + `${counts.not_proven} not proven (of ${counts.total}). Cells are about 55 by 60 km.`;
    $('legend').innerHTML = legendHTML(v, range);
    $('legend').hidden = false;
  } catch (e) {
    hideRegion();
    $('region-note').textContent = e.message;
  }
}

async function loadBorder(regionId) {
  if (!(regionId in state.borders)) {
    const path = REGION_BORDER[regionId];
    state.borders[regionId] = path ? (await loadStatic(path)).geometry : null;
  }
  return state.borders[regionId];
}

function hideRegion() {
  globe.hideCells();
  state.regionShown = null;
  $('region-toggle').textContent = 'Show Egypt trend map';
  $('region-toggle').classList.remove('on');
  $('legend').hidden = true;
  $('region-note').textContent = '';
}

async function openCell(props) {
  const v = currentVar();
  const lat = Number(props.lat), lon = Number(props.lon);
  const label = `Grid cell, ${placeName(lat, lon)} · ${coordText(lat, lon)}`;
  showLoading(panel, `${v.name}, grid cell`);
  try {
    const res = await api.cell(state.regionShown, props.id, v.code);
    showTrend(panel, res, label);
  } catch (e) {
    showCellSummary(panel, props, v, label, `${e.message} The numbers above come from the regional map.`);
  }
}

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
    if (state.regionShown) showRegion(state.regionShown);
    loadPointTrend();
  };
}

async function init() {
  try {
    const [vars, regs, countries, places] = await Promise.all([
      api.variables(), api.regions(), loadStatic('data/countries.geojson'), loadStatic('data/places.json'),
    ]);
    state.variables = vars.variables;
    state.regions = regs.regions;
    state.countries = countries;
    state.places = places;
    fillVariables();
    setupSearch({
      input: $('search-input'), list: $('search-list'), countries, places,
      onPick: (r) => (r.kind === 'country'
        ? select({ kind: 'country', iso: r.iso, bbox: r.bbox, label: r.name })
        : select({ kind: 'city', lat: r.lat, lon: r.lon, label: `${r.name}, ${r.country}`, coords: coordText(r.lat, r.lon) })),
    });
  } catch (e) {
    toast(`Could not reach the server: ${e.message}`);
  }
  $('region-toggle').onclick = () => {
    if (state.regionShown) return hideRegion();
    showRegion('egypt');
    globe.selectCountry('EGY', [24.7, 22, 36.866, 31.586]);
  };
  $('btn-home').onclick = () => globe.home();
  $('btn-proj').onclick = () => { $('btn-proj').textContent = globe.toggleProjection() ? 'Switch to 2D' : 'Switch to 3D'; };
}

init();
window.__cropshift = { globe, state }; // handy for debugging in the browser console
