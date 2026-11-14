// Small geometry helpers: place names for a clicked point, and clipping cells to a border.

const R_KM = 6371;
export function distanceKm(lat1, lon1, lat2, lon2) {
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R_KM * Math.asin(Math.sqrt(a));
}

function inRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Polygon or MultiPolygon geometry -> list of polygons, each a list of rings. */
export function polygonsOf(geometry) {
  return geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
}

// Each geometry's polygons with their bounding boxes, computed once. A border such as Canada's has thousands of
// small island polygons; testing only the ones whose box can contain the point keeps the answer identical and
// makes country maps fast (Canada 41 s -> under 1 s).
const prepared = new WeakMap();
function prepare(geometry) {
  let p = prepared.get(geometry);
  if (!p) {
    p = polygonsOf(geometry).map((poly) => {
      let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
      for (const [x, y] of poly[0]) { if (x < w) w = x; if (x > e) e = x; if (y < s) s = y; if (y > n) n = y; }
      return { poly, box: [w, s, e, n] };
    });
    prepared.set(geometry, p);
  }
  return p;
}

export function inGeometry(lon, lat, geometry) {
  return prepare(geometry).some(({ poly: [outer, ...holes], box: [w, s, e, n] }) => lon >= w && lon <= e && lat >= s && lat <= n
    && inRing(lon, lat, outer) && !holes.some((h) => inRing(lon, lat, h)));
}

/** "Helwan, Egypt", "Near Aswan (40 km), Egypt", or "Red Sea area, near Hurghada (60 km)". */
export function describePlace(lat, lon, countries, places, fallbackCountry = null) {
  const country = countries.features.find((f) => {
    const [w, s, e, n] = f.properties.bbox;
    return lon >= w && lon <= e && lat >= s && lat <= n && inGeometry(lon, lat, f.geometry);
  });
  const cname0 = country ? country.properties.name : null;
  let best = null, bestKm = Infinity;
  for (const [name, pcountry, plat, plon] of places.places) {
    if (Math.abs(plat - lat) > 3) continue;
    if (cname0 && pcountry !== cname0) continue; // inside a country, name the nearest town of that country
    const km = distanceKm(lat, lon, plat, plon);
    if (km < bestKm) { bestKm = km; best = name; }
  }
  const cname = country ? country.properties.name : fallbackCountry;
  if (best && bestKm <= 15) return cname ? `${best}, ${cname}` : best;
  if (best && bestKm <= 250) {
    const near = `near ${best} (${Math.round(bestKm)} km)`;
    return cname ? `${cname}, ${near}` : `Over water, ${near}`;
  }
  return cname || 'Open ocean';
}

/**
 * Cut one grid cell to a border, fast: a cell whose 4 corners agree (all inside or all outside)
 * and that no border vertex falls into is kept whole or dropped without polygon clipping;
 * only cells on the border are clipped exactly. `touched` is a Set of "row,col" keys of cells
 * that contain a border vertex (see borderTouchIndex).
 */
// Neighbouring cells share corners: remember each corner's answer per border.
const corners = new WeakMap();
function cornerInside(x, y, border) {
  let m = corners.get(border);
  if (!m) { m = new Map(); corners.set(border, m); }
  const k = `${x.toFixed(6)},${y.toFixed(6)}`;
  let v = m.get(k);
  if (v === undefined) { v = inGeometry(x, y, border); m.set(k, v); }
  return v;
}

export function cutCell(full, inner, border, touched, key) {
  const [w, s, e, n] = full;
  const ins = [[w, s], [e, s], [e, n], [w, n]].map(([x, y]) => cornerInside(x, y, border));
  const hasVertex = touched.has(key);
  if (!hasVertex && ins.every((v) => !v)) return null;
  if (!hasVertex && ins.every(Boolean)) {
    const [a, b, c, d] = inner;
    return { type: 'Polygon', coordinates: [[[a, b], [c, b], [c, d], [a, d], [a, b]]] };
  }
  const clipped = clipCellToGeometry(inner, border);
  return clipped.geometry && clipped.share >= 0.08 ? clipped.geometry : null;
}

export function borderTouchIndex(border, lat0, lon0, dlat, dlon) {
  const touched = new Set();
  for (const poly of polygonsOf(border)) {
    for (const ring of poly) for (const [x, y] of ring) touched.add(`${Math.round((y - lat0) / dlat)},${Math.round((x - lon0) / dlon)}`);
  }
  return touched;
}

/** Sutherland-Hodgman: the part of a ring inside the box [w, s, e, n], closed (first point repeated). */
function trimRing(ring, w, s, e, n) {
  let pts = ring;
  const edges = [
    (p) => p[0] >= w, (a, b) => [w, a[1] + ((b[1] - a[1]) * (w - a[0])) / (b[0] - a[0])],
    (p) => p[0] <= e, (a, b) => [e, a[1] + ((b[1] - a[1]) * (e - a[0])) / (b[0] - a[0])],
    (p) => p[1] >= s, (a, b) => [a[0] + ((b[0] - a[0]) * (s - a[1])) / (b[1] - a[1]), s],
    (p) => p[1] <= n, (a, b) => [a[0] + ((b[0] - a[0]) * (n - a[1])) / (b[1] - a[1]), n],
  ];
  for (let k = 0; k < 8 && pts.length; k += 2) {
    const inside = edges[k], cross = edges[k + 1], out = [];
    for (let i = 0; i < pts.length; i++) {
      const cur = pts[i], prev = pts[(i + pts.length - 1) % pts.length];
      const ci = inside(cur), pi = inside(prev);
      if (ci) { if (!pi) out.push(cross(prev, cur)); out.push(cur); } else if (pi) out.push(cross(prev, cur));
    }
    pts = out;
  }
  if (!pts.length) return [];
  const [fx, fy] = pts[0], [lx, ly] = pts[pts.length - 1];
  return fx === lx && fy === ly ? pts : [...pts, pts[0]];
}

function ringArea(r) {
  let a = 0;
  for (let i = 0; i < r.length - 1; i++) a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1];
  return Math.abs(a) / 2;
}

/**
 * Clip a rectangle [w, s, e, n] to a country geometry (exact polygon intersection,
 * vendor/polygon-clipping). Returns the clipped geometry (Polygon or MultiPolygon, or
 * null when the cell is outside) and the share of the rectangle that is inside (0 to 1).
 */
export function clipCellToGeometry(bounds, geometry) {
  const [w, s, e, n] = bounds;
  const square = [[[w, s], [e, s], [e, n], [w, n], [w, s]]];
  // Only the polygons whose box overlaps the cell can intersect it (same result, far less work).
  // Each is first trimmed to a box slightly larger than the cell (Sutherland-Hodgman, linear time), so the exact
  // clip below works on a few vertices instead of the whole coastline; the margin keeps trimming seams outside the cell.
  const m = Math.max(e - w, n - s) * 0.05;
  const near = [];
  for (const { poly, box } of prepare(geometry)) {
    if (box[0] > e || box[2] < w || box[1] > n || box[3] < s) continue;
    const rings = poly.map((r) => trimRing(r, w - m, s - m, e + m, n + m));
    if (rings[0].length >= 4) near.push([rings[0], ...rings.slice(1).filter((r) => r.length >= 4)]);
  }
  if (!near.length) return { geometry: null, share: 0 };
  // eslint-disable-next-line no-undef
  const pieces = polygonClipping.intersection(square, near).filter((p) => ringArea(p[0]) > 1e-6);
  if (!pieces.length) return { geometry: null, share: 0 };
  const area = pieces.reduce((t, p) => t + ringArea(p[0]) - p.slice(1).reduce((h, r) => h + ringArea(r), 0), 0);
  return {
    geometry: pieces.length === 1 ? { type: 'Polygon', coordinates: pieces[0] } : { type: 'MultiPolygon', coordinates: pieces },
    share: area / ((e - w) * (n - s)),
  };
}
