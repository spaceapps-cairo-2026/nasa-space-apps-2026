// The 3D globe (MapLibre GL JS 5.6, globe projection) with NASA GIBS imagery.
/* global maplibregl */

const GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg';
// Sharp close-up imagery: Sentinel-2 cloudless mosaic (about 10 m per pixel), free for non-commercial use with credit.
const S2 = 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg';
const S2_CREDIT = '<a href="https://s2maps.eu" target="_blank" rel="noopener">Sentinel-2 cloudless by EOX</a> (Contains modified Copernicus Sentinel data 2020)';
// Fallback when EOX is blocked: NASA VIIRS true color for one clear summer day (about 375 m per pixel).
const VIIRS_DATE = '2025-07-20';
const VIIRS = `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/${VIIRS_DATE}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`;
const EMPTY = { type: 'FeatureCollection', features: [] };
const CLOSE_UP_OPACITY = ['interpolate', ['linear'], ['zoom'], 4.5, 0, 6, 1];
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
          s2: { type: 'raster', tiles: [S2], tileSize: 256, minzoom: 4, maxzoom: 15, attribution: S2_CREDIT },
          viirs: { type: 'raster', tiles: [VIIRS], tileSize: 256, maxzoom: 9, attribution: `Close-up imagery: NASA GIBS, VIIRS ${VIIRS_DATE}` },
          countries: { type: 'geojson', data: 'data/countries.geojson', attribution: 'Borders: Natural Earth' },
          selection: { type: 'geojson', data: EMPTY },
          cells: { type: 'geojson', data: EMPTY },
          regionBorder: { type: 'geojson', data: EMPTY },
        },
        layers: [
          { id: 'gibs', type: 'raster', source: 'gibs' },
          // Fades in between zoom 4.5 and 6, when Blue Marble (500 m pixels) starts to look blurry.
          { id: 'viirs', type: 'raster', source: 'viirs', minzoom: 4.5, layout: { visibility: 'none' },
            paint: { 'raster-opacity': CLOSE_UP_OPACITY, 'raster-fade-duration': 200 } },
          { id: 's2', type: 'raster', source: 's2', minzoom: 4.5,
            paint: { 'raster-opacity': CLOSE_UP_OPACITY, 'raster-fade-duration': 200 } },
          { id: 'countries-line', type: 'line', source: 'countries', paint: { 'line-color': '#ffffff', 'line-opacity': 0.28, 'line-width': 0.8 } },
          { id: 'country-hl', type: 'line', source: 'countries', filter: ['==', ['get', 'iso'], ''], paint: { 'line-color': '#6fd3ff', 'line-width': 2.5 } },
          { id: 'selection-fill', type: 'fill', source: 'selection', paint: { 'fill-color': '#6fd3ff', 'fill-opacity': 0.15 } },
          { id: 'selection-line', type: 'line', source: 'selection', paint: { 'line-color': '#6fd3ff', 'line-width': 2 } },
          // Not proven cells: flat, see-through tiles so the land shows through.
          { id: 'cells-flat', type: 'fill', source: 'cells', filter: ['==', ['get', 'flat'], true],
            paint: { 'fill-color': ['get', 'color'], 'fill-opacity': ['coalesce', ['get', 'opacity'], 0.38], 'fill-outline-color': 'rgba(255,255,255,0.25)' } },
          // Invisible flat layer for clicks: MapLibre 5.6 cannot pick fill-extrusion in globe mode.
          { id: 'cells-hit', type: 'fill', source: 'cells', paint: { 'fill-color': '#000', 'fill-opacity': 0.01 } },
          // Proven changes: raised columns.
          { id: 'cells', type: 'fill-extrusion', source: 'cells', filter: ['!=', ['get', 'flat'], true],
            paint: { 'fill-extrusion-color': ['get', 'color'], 'fill-extrusion-height': ['get', 'height'], 'fill-extrusion-opacity': 0.88,
              'fill-extrusion-vertical-gradient': true } },
          // Detailed border of the region on top of everything.
          { id: 'region-border', type: 'line', source: 'regionBorder', paint: { 'line-color': '#ffffff', 'line-width': 1.6, 'line-opacity': 0.9 } },
        ],
      },
      ...HOME,
      maxPitch: 70,
      maxZoom: 14,
      attributionControl: { compact: true },
    });
    this.map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');
    // Map credits start folded into the (i) button (tap it to read them), so the long credit line never runs
    // under the sidebar or the place panel. MapLibre itself folds them on the first drag of the map.
    this.map.once('load', () => document.querySelectorAll('.maplibregl-ctrl-attrib.maplibregl-compact-show')
      .forEach((el) => { el.classList.remove('maplibregl-compact-show'); el.removeAttribute('open'); }));
    this.watchCloseUpImagery();

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

  /** Use Sentinel-2 when its server answers; after a few failures and no success, switch to NASA VIIRS. */
  watchCloseUpImagery() {
    let ok = false, errors = 0;
    this.closeUpImagery = 'sentinel-2';
    this.map.on('sourcedata', (e) => { if (e.sourceId === 's2' && e.tile && e.tile.state === 'loaded') ok = true; });
    this.map.on('error', (e) => {
      if (e.sourceId !== 's2' || ok || this.closeUpImagery !== 'sentinel-2') return;
      errors += 1;
      if (errors < 3) return;
      this.closeUpImagery = 'viirs';
      this.map.removeLayer('s2');
      this.map.removeSource('s2');
      this.map.setLayoutProperty('viirs', 'visibility', 'visible');
    });
  }

  pin(lon, lat) {
    if (!this.marker) {
      const el = document.createElement('div');
      el.className = 'pin';
      this.marker = new maplibregl.Marker({ element: el });
    }
    this.marker.setLngLat([lon, lat]).addTo(this.map);
  }

  /**
   * Run a map change now, or retry until the map has finished loading its style. Changes on the
   * same channel replace each other (the newest wins), so a quick click sequence cannot leave an
   * old layer on screen.
   */
  when(channel, fn) {
    this.pending = this.pending || {};
    const token = Symbol(channel);
    this.pending[channel] = token;
    const attempt = (tries) => {
      if (this.pending[channel] !== token) return; // superseded by a newer change
      try { fn(); } catch (e) {
        if (tries > 0) setTimeout(() => attempt(tries - 1), 150);
        else console.error(e);
      }
    };
    attempt(100);
  }

  clearSelectionNow() {
    this.map.getSource('selection').setData(EMPTY);
    this.map.setFilter('country-hl', ['==', ['get', 'iso'], '']);
    if (this.marker) this.marker.remove();
  }

  clearSelection() { this.when('selection', () => this.clearSelectionNow()); }

  selectPoint(lon, lat, fly = false) {
    this.when('selection', () => { this.clearSelectionNow(); this.pin(lon, lat); });
    if (fly) this.map.flyTo({ center: [lon, lat], zoom: Math.max(this.map.getZoom(), 4), duration: 2200, essential: true });
  }

  selectCity(lon, lat, km = 30) {
    this.when('selection', () => {
      this.clearSelectionNow();
      this.pin(lon, lat);
      this.map.getSource('selection').setData(circle(lon, lat, km));
    });
    // Close-up imagery is sharp at this zoom, so the 30 km circle fills the view.
    this.map.flyTo({ center: [lon, lat], zoom: 8.5, pitch: 0, duration: 2800, essential: true });
  }

  selectCountry(iso, bbox) {
    this.when('selection', () => {
      this.clearSelectionNow();
      this.map.setFilter('country-hl', ['==', ['get', 'iso'], iso]);
    });
    this.map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 80, pitch: 35, duration: 2600, essential: true, maxZoom: 6 });
  }

  /** Whole-Earth trend layer (an image), visible when zoomed out, fading out as you zoom in. */
  showWorld({ url, coordinates }) {
    this.when('world', () => {
      if (this.map.getSource('world')) {
        this.map.getSource('world').updateImage({ url, coordinates });
        this.map.setLayoutProperty('world', 'visibility', 'visible');
        return;
      }
      this.map.addSource('world', { type: 'image', url, coordinates });
      this.map.addLayer({ id: 'world', type: 'raster', source: 'world',
        paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 2.8, 0.85, 4.2, 0], 'raster-fade-duration': 0 } }, 'countries-line');
    });
  }

  hideWorld() {
    this.when('world', () => { if (this.map.getLayer('world')) this.map.setLayoutProperty('world', 'visibility', 'none'); });
  }

  showCells(fc, border = null) {
    this.when('cells', () => {
      this.map.getSource('cells').setData(fc);
      this.map.getSource('regionBorder').setData(border ? { type: 'Feature', properties: {}, geometry: border } : EMPTY);
    });
  }

  hideCells() {
    this.when('cells', () => {
      this.map.getSource('cells').setData(EMPTY);
      this.map.getSource('regionBorder').setData(EMPTY);
    });
  }

  flyToCell(lon, lat) {
    this.map.flyTo({ center: [lon, lat], zoom: Math.max(this.map.getZoom(), 6.2), pitch: 45, duration: 1800, essential: true });
    this.pin(lon, lat);
  }

  home() { this.map.flyTo({ ...HOME, duration: 2200, essential: true }); }

  toggleProjection() {
    this.globe = !this.globe;
    this.map.setProjection({ type: this.globe ? 'globe' : 'mercator' });
    return this.globe;
  }
}
