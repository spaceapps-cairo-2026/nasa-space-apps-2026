// Export a country's trend map for Blender, cut to the border exactly like the web app.
//
// Run from the repo root:   node demo/blender/export_for_blender.cjs
// Input:  a trend_region answer from lane A's engine (contracts/api.md). Default:
//         contracts/fixtures/trend_region.json (Egypt, made by the real engine, method D1).
//         For a fresh answer:  curl "http://localhost:8000/api/trend/region?lat_min=22&lat_max=31.586&lon_min=24.7&lon_max=36.866&variable=T2M" -o demo/blender/data/egypt_region_full.json
//                              node demo/blender/export_for_blender.cjs egypt.json
// Output: demo/blender/data/egypt_cells.geojson, egypt_border.geojson, summary.json
const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..', '..');
// Default: the full Egypt box as the app requests it (22 to 31.6 N, 24.7 to 36.9 E), saved from the real engine.
const INPUT = process.argv[2] || path.join(__dirname, 'data', 'egypt_region_full.json');
const BORDER_JSON = path.join(REPO, 'app', 'data', 'regions', 'EGY.geojson');
const polygonClipping = require(path.join(REPO, 'app', 'vendor', 'polygon-clipping.umd.min.js'));
const OUT = path.join(__dirname, 'data');

const ringArea = (r) => Math.abs(r.slice(0, -1).reduce((a, p, i) => a + p[0] * r[i + 1][1] - r[i + 1][0] * p[1], 0)) / 2;
const polysOf = (g) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates);
const CONF = { 2: 'strong', 1: 'moderate', 0: 'not_proven' };

const g = JSON.parse(fs.readFileSync(INPUT, 'utf8'));
const border = JSON.parse(fs.readFileSync(BORDER_JSON, 'utf8')).geometry;
fs.mkdirSync(OUT, { recursive: true });

const G = g.grid;
const dlat = G.lat_step, dlon = G.lon_step;
const gap = Math.min(0.025, dlon * 0.04);
const kept = [];
for (let i = 0; i < G.lats.length; i++) {
  for (let j = 0; j < G.lons.length; j++) {
    const level = G.level[i][j], slope = G.slope_per_decade[i][j];
    if (level === null || level < 0 || slope === null) continue;
    const lat = G.lats[i], lon = G.lons[j];
    const [w, s, e, n] = [lon - dlon / 2 + gap, lat - dlat / 2 + gap, lon + dlon / 2 - gap, lat + dlat / 2 - gap];
    const pieces = polygonClipping.intersection([[[w, s], [e, s], [e, n], [w, n], [w, s]]], polysOf(border))
      .filter((p) => ringArea(p[0]) > 1e-6);
    if (!pieces.length) continue;
    const share = pieces.reduce((t, p) => t + ringArea(p[0]), 0) / ((e - w) * (n - s));
    if (share < 0.08) continue;
    kept.push({ lat, lon, slope, q: G.q ? G.q[i][j] : null, confidence: CONF[level], pieces });
  }
}
const proven = kept.filter((c) => c.confidence !== 'not_proven');
const sorted = proven.map((c) => Math.abs(c.slope)).sort((a, b) => a - b);
const range = sorted.length ? sorted[Math.floor(0.95 * (sorted.length - 1))] : 1; // same scale rule as the app

const features = kept.map((c) => ({
  type: 'Feature',
  properties: {
    id: `cell_${c.lat}_${c.lon}`, lat: c.lat, lon: c.lon,
    slope_per_decade: c.slope, q: c.q, confidence: c.confidence,
    direction: c.confidence === 'not_proven' ? 'no_clear_trend' : c.slope > 0 ? 'increasing' : 'decreasing',
    strength: c.confidence === 'not_proven' ? 0 : Number(Math.min(1, Math.abs(c.slope) / range).toFixed(4)),
  },
  geometry: c.pieces.length === 1 ? { type: 'Polygon', coordinates: c.pieces[0] } : { type: 'MultiPolygon', coordinates: c.pieces },
}));

const counts = {
  total: features.length,
  rising: proven.filter((c) => c.slope > 0).length,
  falling: proven.filter((c) => c.slope < 0).length,
  not_proven: kept.length - proven.length,
};
const fastest = proven.sort((a, b) => b.slope - a.slope)[0];

fs.writeFileSync(path.join(OUT, 'egypt_cells.geojson'), JSON.stringify({ type: 'FeatureCollection', features }));
fs.writeFileSync(path.join(OUT, 'egypt_border.geojson'), JSON.stringify({ type: 'Feature', properties: { name: 'Egypt' }, geometry: border }));
fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify({
  source_file: path.relative(REPO, INPUT), variable: g.variable.name, unit: g.variable.unit === 'C' ? '°C' : g.variable.unit, period: g.period,
  method: g.method, counts, color_scale_max_slope_per_decade: Number(range.toFixed(3)),
  fastest_cell: fastest ? { lat: fastest.lat, lon: fastest.lon, slope_per_decade: fastest.slope, q: fastest.q } : null,
  note: 'Copy on-screen numbers from here. Re-run this export when the backend is final.',
}, null, 1));
console.log('cells:', counts, '| fastest:', fastest && `${fastest.slope} per decade at ${fastest.lat}N ${fastest.lon}E`);
