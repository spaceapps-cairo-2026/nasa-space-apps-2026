// CropShift Earth: wires the globe, search and the Trends tab together.
import { api, loadStatic } from './api.js';
import { Globe } from './globe.js';
import { setupSearch } from './search.js';
import { cellsToGeoJSON, legendHTML, showCellSummary, showLoading, showMessage, showTrend } from './trends.js';

const $ = (id) => document.getElementById(id);
const REGION_FOR_ISO = { EGY: 'egypt' };

const state = {
  variables: [],
  regions: [],
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

const globe = new Globe('globe', {
  onPoint: (ll) => select({ kind: 'point', lat: ll.lat, lon: ll.lng, label: `${ll.lat.toFixed(2)}°, ${ll.lng.toFixed(2)}°` }),
  onCell: (props) => openCell(props),
});

async function loadPointTrend() {
  const s = state.selection;
  if (!s || s.kind === 'country') return;
  const v = currentVar();
  showLoading(panel, `${v.name} at ${s.label}`);
  try {
    const res = await api.point(s.lat, s.lon, v.code, s.label);
    showTrend(panel, res, res.mock ? `${s.label} (sample shows Cairo)` : s.label);
  } catch (e) {
    showMessage(panel, `${v.name} at ${s.label}`, e.message, 'warn');
  }
}

function select(sel) {
  state.selection = sel;
  const kindText = { point: 'Point', city: 'City (30 km around the center)', country: 'Country' }[sel.kind];
  $('selection-text').textContent = `${sel.label} · ${kindText}`;
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
    const region = await api.region(regionId, v.code);
    const { fc, range } = cellsToGeoJSON(region);
    globe.showCells(fc);
    state.regionShown = regionId;
    btn.textContent = 'Hide Egypt trend map';
    btn.classList.add('on');
    const s = region.summary;
    $('region-note').textContent = `${s.n_increasing} cells rising, ${s.n_decreasing} falling, ${s.n_not_proven} not proven (of ${s.n_cells}).`;
    $('legend').innerHTML = legendHTML(v, range);
    $('legend').hidden = false;
  } catch (e) {
    hideRegion();
    $('region-note').textContent = e.message;
  }
}

function hideRegion() {
  globe.hideCells();
  state.regionShown = null;
  $('region-toggle').textContent = 'Show Egypt trend map';
  $('region-toggle').classList.remove('on');
  $('legend').hidden = true;
}

async function openCell(props) {
  const v = currentVar();
  showLoading(panel, `${v.name}, grid cell`);
  try {
    const res = await api.cell(state.regionShown, props.id, v.code);
    showTrend(panel, res, `Grid cell ${Number(props.lat).toFixed(2)}° N, ${Number(props.lon).toFixed(2)}° E`);
  } catch (e) {
    showCellSummary(panel, props, v, `${e.message} The numbers above come from the regional map.`);
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
    fillVariables();
    setupSearch({
      input: $('search-input'), list: $('search-list'), countries, places,
      onPick: (r) => (r.kind === 'country'
        ? select({ kind: 'country', iso: r.iso, bbox: r.bbox, label: r.name })
        : select({ kind: 'city', lat: r.lat, lon: r.lon, label: `${r.name}, ${r.country}` })),
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
