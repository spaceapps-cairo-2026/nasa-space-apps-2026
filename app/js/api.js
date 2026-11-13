// Talks to the backend only through the endpoints in contracts/api.md (v0.4).

async function getJSON(path, params = {}) {
  const url = new URL(path, window.location.origin);
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined) url.searchParams.set(k, v);
  const res = await fetch(url);
  let body = null;
  try { body = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    const err = new Error((body && body.detail) || `The server answered ${res.status}.`);
    err.status = res.status;
    throw err;
  }
  return body;
}

export const api = {
  health: () => getJSON('/health'),
  variables: () => getJSON('/api/variables'),
  // Lane A contract v0.4 (contracts/api.md).
  point: (lat, lon, v) => getJSON('/api/trend/point', { lat: lat.toFixed(4), lon: lon.toFixed(4), variable: v }),
  // bbox = [west, south, east, north]; the backend live-fetches NASA data for that box.
  // country (ISO code, v0.4): the test, the counts and the average then cover that country only, not the whole box.
  region: (bbox, v, country = null) => getJSON('/api/trend/region', {
    lat_min: bbox[1].toFixed(3), lat_max: bbox[3].toFixed(3), lon_min: bbox[0].toFixed(3), lon_max: bbox[2].toFixed(3), variable: v, country,
  }),
  world: (v, stride = 2) => getJSON('/api/trend/world', { variable: v, stride }),
  // There is no cell endpoint: a cell's own series is the point trend at its center (same grid cell).
  cell: (lat, lon, v) => getJSON('/api/trend/point', { lat: lat.toFixed(4), lon: lon.toFixed(4), variable: v }),
  // Lane B additions.
  farming: (country) => getJSON('/api/farming', { country }),
  validation: () => getJSON('/api/validation'),
};

export async function loadStatic(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Could not load ${path}`);
  return res.json();
}
