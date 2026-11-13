// Talks to the backend only through the endpoints in contracts/api.md (v0.3).

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
  variables: () => getJSON('/api/variables'),
  regions: () => getJSON('/api/regions'),
  point: (lat, lon, v, name) => getJSON('/api/trend/point', { lat: lat.toFixed(4), lon: lon.toFixed(4), var: v, name }),
  // bbox = [west, south, east, north]; the backend live-fetches NASA data for that box.
  region: (bbox, v, name) => getJSON('/api/trend/region', {
    west: bbox[0].toFixed(3), south: bbox[1].toFixed(3), east: bbox[2].toFixed(3), north: bbox[3].toFixed(3), var: v, name,
  }),
  world: (v) => getJSON('/api/trend/world', { var: v }),
  farming: (country) => getJSON('/api/farming', { country }),
  validation: () => getJSON('/api/validation'),
  cell: (lat, lon, v) => getJSON('/api/trend/cell', { lat: lat.toFixed(3), lon: lon.toFixed(3), var: v }),
};

export async function loadStatic(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Could not load ${path}`);
  return res.json();
}
