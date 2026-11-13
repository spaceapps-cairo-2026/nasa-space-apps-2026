// The 3D globe (MapLibre GL JS 5.6, globe projection) with NASA GIBS imagery.
/* global maplibregl */

const GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg';
const EMPTY = { type: 'FeatureCollection', features: [] };
export const HOME = { center: [20, 18], zoom: 1.4, pitch: 0, bearing: 0 };

function circle(lon, lat, km, steps = 72) {
  const coords = [];
  const dLat = km / 110.574;
  const dLon = km / (111.32 * Math.cos((lat * Math.PI) / 180));
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    coords.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [coords] } };
}

export class Globe {
  constructor(container, { onPoint, onCell }) {
    this.globe = true;
    this.marker = null;
    this.map = new maplibregl.Map({
      container,
      style: {
        version: 8,
        projection: { type: 'globe' },
        sky: { 'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 7, 0] },
        sources: {
          gibs: { type: 'raster', tiles: [GIBS], tileSize: 256, maxzoom: 8, attribution: 'Imagery: NASA GIBS, Blue Marble' },
          countries: { type: 'geojson', data: 'data/countries.geojson', attribution: 'Borders: Natural Earth' },
          selection: { type: 'geojson', data: EMPTY },
          cells: { type: 'geojson', data: EMPTY },
        },
        layers: [
          { id: 'gibs', type: 'raster', source: 'gibs' },
          { id: 'countries-line', type: 'line', source: 'countries', paint: { 'line-color': '#ffffff', 'line-opacity': 0.28, 'line-width': 0.8 } },
          { id: 'country-hl', type: 'line', source: 'countries', filter: ['==', ['get', 'iso'], ''], paint: { 'line-color': '#6fd3ff', 'line-width': 2.5 } },
          { id: 'selection-fill', type: 'fill', source: 'selection', paint: { 'fill-color': '#6fd3ff', 'fill-opacity': 0.15 } },
          { id: 'selection-line', type: 'line', source: 'selection', paint: { 'line-color': '#6fd3ff', 'line-width': 2 } },
          // Invisible flat layer for clicks: MapLibre 5.6 cannot pick fill-extrusion in globe mode.
          { id: 'cells-hit', type: 'fill', source: 'cells', paint: { 'fill-color': '#000', 'fill-opacity': 0.01 } },
          { id: 'cells', type: 'fill-extrusion', source: 'cells',
            paint: { 'fill-extrusion-color': ['get', 'color'], 'fill-extrusion-height': ['get', 'height'], 'fill-extrusion-opacity': 0.9 } },
        ],
      },
      ...HOME,
      maxPitch: 70,
      attributionControl: { compact: true },
    });
    this.map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');

    let cellClicked = false;
    this.map.on('click', 'cells-hit', (e) => {
      if (!e.features || !e.features[0]) return;
      cellClicked = true;
      onCell(e.features[0].properties);
    });
    this.map.on('click', (e) => {
      setTimeout(() => {
        if (!cellClicked) onPoint(e.lngLat.wrap());
        cellClicked = false;
      }, 0);
    });
    this.map.on('mouseenter', 'cells-hit', () => { this.map.getCanvas().style.cursor = 'pointer'; });
    this.map.on('mouseleave', 'cells-hit', () => { this.map.getCanvas().style.cursor = ''; });
  }

  pin(lon, lat) {
    if (!this.marker) {
      const el = document.createElement('div');
      el.className = 'pin';
      this.marker = new maplibregl.Marker({ element: el });
    }
    this.marker.setLngLat([lon, lat]).addTo(this.map);
  }

  clearSelection() {
    this.map.getSource('selection')?.setData(EMPTY);
    this.map.setFilter('country-hl', ['==', ['get', 'iso'], '']);
    if (this.marker) this.marker.remove();
  }

  selectPoint(lon, lat, fly = false) {
    this.clearSelection();
    this.pin(lon, lat);
    if (fly) this.map.flyTo({ center: [lon, lat], zoom: Math.max(this.map.getZoom(), 4), duration: 2200, essential: true });
  }

  selectCity(lon, lat, km = 30) {
    this.clearSelection();
    this.pin(lon, lat);
    this.map.getSource('selection').setData(circle(lon, lat, km));
    // GIBS Blue Marble is ~500 m per pixel, so closer than zoom 6 only looks blurry.
    this.map.flyTo({ center: [lon, lat], zoom: 6, pitch: 0, duration: 2600, essential: true });
  }

  selectCountry(iso, bbox) {
    this.clearSelection();
    this.map.setFilter('country-hl', ['==', ['get', 'iso'], iso]);
    this.map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 80, pitch: 35, duration: 2600, essential: true, maxZoom: 6 });
  }

  showCells(fc) { this.map.getSource('cells').setData(fc); }
  hideCells() { this.map.getSource('cells').setData(EMPTY); }

  home() { this.map.flyTo({ ...HOME, duration: 2200, essential: true }); }

  toggleProjection() {
    this.globe = !this.globe;
    this.map.setProjection({ type: this.globe ? 'globe' : 'mercator' });
    return this.globe;
  }
}
