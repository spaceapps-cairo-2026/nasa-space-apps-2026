// One-time edit of the app's map data (asked by Mada, Sat 14 Nov 2026):
//   - the country is named Palestine only: Natural Earth's "Israel" shape and its "Palestine" shape (West Bank, Gaza)
//     become ONE country, iso PSE, name Palestine;
//   - the Golan Heights, which Natural Earth draws inside the Israel shape, go to Syria (their status under UN resolutions).
// The Golan's western edge is our approximation of the 1949 armistice line (Banias, the upper Jordan, the east shore of
// Lake Tiberias, the Yarmouk), good to about 1 to 2 km; the eastern edge is Natural Earth's own line. Map cells are 55 km.
//
// Run from the repo root (no install needed: uses the polygon-clipping library already bundled in app/vendor):
//     node scripts/palestine_borders.js
// It changes app/data/countries.geojson, app/data/borders_50m.geojson and app/data/places.json, and is safe to run twice.
const fs = require('fs');
const path = require('path');
const pc = require(path.join(__dirname, '..', 'app', 'vendor', 'polygon-clipping.umd.min.js'));

const ROOT = path.join(__dirname, '..');
const GOLAN_CUT = [[[35.64, 33.45], [36.30, 33.45], [36.30, 32.55], [35.66, 32.55], [35.66, 32.68], [35.64, 32.72],
  [35.65, 32.85], [35.63, 32.90], [35.63, 33.10], [35.64, 33.25], [35.64, 33.45]]];

const asMulti = (g) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates);
const toGeometry = (multi) => (multi.length === 1 ? { type: 'Polygon', coordinates: multi[0] } : { type: 'MultiPolygon', coordinates: multi });
const round = (multi) => multi.map((poly) => poly.map((ring) => ring.map(([x, y]) => [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000])));
function bbox(multi) {
  const pts = multi.flat(2);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)].map((v) => Math.round(v * 1000) / 1000);
}

function fixBorders(file) {
  const full = path.join(ROOT, file);
  const data = JSON.parse(fs.readFileSync(full, 'utf8'));
  const isr = data.features.find((f) => f.properties.iso === 'ISR');
  if (!isr) { console.log(`${file}: already done`); return; }
  const pse = data.features.find((f) => f.properties.iso === 'PSE');
  const syr = data.features.find((f) => f.properties.iso === 'SYR');
  const golan = pc.intersection(asMulti(isr.geometry), GOLAN_CUT);
  const rest = pc.difference(asMulti(isr.geometry), GOLAN_CUT);
  const palestine = round(pc.union(rest, asMulti(pse.geometry)));
  const syria = round(pc.union(asMulti(syr.geometry), golan));
  pse.geometry = toGeometry(palestine);
  pse.properties.name = 'Palestine';
  syr.geometry = toGeometry(syria);
  for (const [f, multi] of [[pse, palestine], [syr, syria]]) if ('bbox' in f.properties) f.properties.bbox = bbox(multi);
  data.features = data.features.filter((f) => f !== isr);
  fs.writeFileSync(full, JSON.stringify(data));
  console.log(`${file}: Palestine ${JSON.stringify(bbox(palestine))}, Golan to Syria (${golan.length} part)`);
}

fixBorders('app/data/countries.geojson');
fixBorders('app/data/borders_50m.geojson');

const placesFile = path.join(ROOT, 'app', 'data', 'places.json');
const places = JSON.parse(fs.readFileSync(placesFile, 'utf8'));
let n = 0;
for (const p of places.places) if (p[1] === 'Israel') { p[1] = 'Palestine'; n += 1; }
fs.writeFileSync(placesFile, JSON.stringify(places));
console.log(`places.json: ${n} cities now in Palestine`);
