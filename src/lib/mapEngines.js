import { loadGoogleMaps } from './googleMaps';

const DASH = { dash: '12 10', dot: '1 9', short: '3 8' };
const FIT_PADDING = 28;

export async function createLeafletEngine(el, { isCancelled } = {}) {
  const [{ default: L }] = await Promise.all([import('leaflet'), import('leaflet/dist/leaflet.css')]);
  if (isCancelled?.()) return null;

  const touch = window.matchMedia('(pointer: coarse)').matches;
  const map = L.map(el, { zoomControl: false, zoomSnap: 0.25, scrollWheelZoom: false, dragging: !touch, tap: false }).setView(
    [4.5585, -74.1535],
    13
  );
  L.control.zoom({ position: 'topright' }).addTo(map);
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);

  const toggle = layer => ({ show: on => (on ? layer.addTo(map) : layer.remove()) });

  return {
    polyline({ path, color, weight = 5, opacity = 0.95, dash = null, flow = false, casing = false, glow = false }) {
      const group = L.layerGroup();
      const shape = { lineCap: 'round', lineJoin: 'round', interactive: false };
      if (casing) L.polyline(path, { ...shape, color: '#fff', weight: weight + 5, opacity: 0.9 }).addTo(group);
      const flowClass = flow ? (dash === 'dot' ? 'lf-route--dot' : 'lf-route--flow') : '';
      L.polyline(path, {
        ...shape,
        color,
        weight,
        opacity,
        dashArray: DASH[dash] ?? null,
        className: [flowClass, glow ? 'lf-glow' : ''].join(' ').trim()
      }).addTo(group);
      group.addTo(map);
      return toggle(group);
    },
    marker({ pos, html, title, onClick, z = 0 }) {
      const m = L.marker(pos, {
        icon: L.divIcon({ className: 'map-icon', html, iconSize: null }),
        title,
        keyboard: false,
        interactive: Boolean(onClick),
        zIndexOffset: z * 1000
      }).addTo(map);
      if (onClick) m.on('click', onClick);
      return { ...toggle(m), get el() { return m.getElement(); } };
    },
    vehicle({ pos, color }) {
      const v = L.circleMarker(pos, { radius: 6, color, weight: 3, fillColor: '#fff', fillOpacity: 1, interactive: false }).addTo(map);
      return { ...toggle(v), setPos: p => v.setLatLng(p) };
    },
    fit(points) {
      map.fitBounds(L.latLngBounds(points.map(p => [p.lat, p.lng])), { padding: [FIT_PADDING, FIT_PADDING] });
    },
    flyTo(pos, zoom) {
      map.flyTo(pos, zoom, { duration: 0.8 });
    },
    onReady(cb) {
      tiles.once('load', cb);
    },
    destroy() {
      map.remove();
    }
  };
}

export async function createGoogleEngine(el, { apiKey, mapId, onAuthFailure, isCancelled }) {
  window.gm_authFailure = onAuthFailure;
  const maps = await loadGoogleMaps(apiKey);
  const { Map } = await maps.importLibrary('maps');
  const { AdvancedMarkerElement } = await maps.importLibrary('marker');
  if (isCancelled?.()) return null;

  const map = new Map(el, { mapId, disableDefaultUI: true, zoomControl: true, gestureHandling: 'cooperative', clickableIcons: false });

  const flowing = [];
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let tick = 0;
  const timer = reduced
    ? null
    : setInterval(() => {
        tick += 1;
        flowing.forEach(p => {
          const icons = p.get('icons');
          icons[0].offset = `${(tick * 1.1) % 22}px`;
          p.set('icons', icons);
        });
      }, 50);

  const dashIcon = (dash, color, weight) =>
    dash === 'dot'
      ? { icon: { path: maps.SymbolPath.CIRCLE, scale: weight * 0.45, fillColor: color, fillOpacity: 1, strokeOpacity: 0 }, offset: '0', repeat: '10px' }
      : { icon: { path: 'M 0,-1 0,1', strokeColor: color, strokeOpacity: 1, strokeWeight: weight, scale: dash === 'short' ? 1.5 : 3 }, offset: '0', repeat: dash === 'short' ? '11px' : '22px' };

  const toggle = items => ({ show: on => items.forEach(i => (i.setMap ? i.setMap(on ? map : null) : (i.map = on ? map : null))) });

  return {
    polyline({ path, color, weight = 5, opacity = 0.95, dash = null, flow = false, casing = false, z = 2 }) {
      const items = [];
      if (casing) items.push(new maps.Polyline({ map, path, strokeColor: '#fff', strokeOpacity: 0.9, strokeWeight: weight + 5, zIndex: z }));
      const line = new maps.Polyline({
        map,
        path,
        strokeColor: color,
        strokeOpacity: dash ? 0 : opacity,
        strokeWeight: weight,
        zIndex: z + 1,
        icons: dash ? [dashIcon(dash, color, weight)] : []
      });
      if (dash && flow) flowing.push(line);
      items.push(line);
      return toggle(items);
    },
    marker({ pos, html, title, onClick, z = 0 }) {
      const wrap = document.createElement('div');
      wrap.className = 'map-icon map-icon--google';
      wrap.innerHTML = html;
      const m = new AdvancedMarkerElement({ map, position: pos, content: wrap, title, zIndex: 10 + z, gmpClickable: Boolean(onClick) });
      if (onClick) m.addListener('click', onClick);
      return { ...toggle([m]), el: wrap };
    },
    vehicle({ pos, color }) {
      const dot = document.createElement('div');
      dot.className = 'map-vehicle';
      dot.style.setProperty('--c', color);
      const m = new AdvancedMarkerElement({ map, position: pos, content: dot, zIndex: 5 });
      return { ...toggle([m]), setPos: p => (m.position = p) };
    },
    fit(points) {
      const bounds = new maps.LatLngBounds();
      points.forEach(p => bounds.extend(p));
      map.fitBounds(bounds, FIT_PADDING);
    },
    flyTo(pos, zoom) {
      map.panTo(pos);
      map.setZoom(Math.round(zoom));
    },
    onReady(cb) {
      maps.event.addListenerOnce(map, 'tilesloaded', cb);
    },
    destroy() {
      clearInterval(timer);
    }
  };
}
