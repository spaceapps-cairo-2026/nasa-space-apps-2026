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

export function inGeometry(lon, lat, geometry) {
  return polygonsOf(geometry).some(([outer, ...holes]) => inRing(lon, lat, outer) && !holes.some((h) => inRing(lon, lat, h)));
}

/** "Helwan, Egypt", "Near Aswan (40 km), Egypt", or "Red Sea area, near Hurghada (60 km)". */
export function describePlace(lat, lon, countries, places) {
  const country = countries.features.find((f) => {
    const [w, s, e, n] = f.properties.bbox;
    return lon >= w && lon <= e && lat >= s && lat <= n && inGeometry(lon, lat, f.geometry);
  });
  let best = null, bestKm = Infinity;
  for (const [name, , plat, plon] of places.places) {
    if (Math.abs(plat - lat) > 3) continue;
    const km = distanceKm(lat, lon, plat, plon);
    if (km < bestKm) { bestKm = km; best = name; }
  }
  const cname = country ? country.properties.name : null;
  if (best && bestKm <= 15) return cname ? `${best}, ${cname}` : best;
  if (best && bestKm <= 250) {
    const near = `near ${best} (${Math.round(bestKm)} km)`;
    return cname ? `${cname}, ${near}` : `Over water, ${near}`;
  }
  return cname || 'Open ocean';
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
  // eslint-disable-next-line no-undef
  const pieces = polygonClipping.intersection(square, polygonsOf(geometry)).filter((p) => ringArea(p[0]) > 1e-6);
  if (!pieces.length) return { geometry: null, share: 0 };
  const area = pieces.reduce((t, p) => t + ringArea(p[0]) - p.slice(1).reduce((h, r) => h + ringArea(r), 0), 0);
  return {
    geometry: pieces.length === 1 ? { type: 'Polygon', coordinates: pieces[0] } : { type: 'MultiPolygon', coordinates: pieces },
    share: area / ((e - w) * (n - s)),
  };
}
