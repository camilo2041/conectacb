import { inCB, toLatLng } from '../data/mapStyle';

// En producción nginx reenvía /api al contenedor de la API; en desarrollo lo hace el proxy de Vite.
const BASE = import.meta.env.VITE_API_URL || '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers }
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    // Los 4xx traen un mensaje pensado para el usuario; los 5xx son fallas internas.
    const detail = res.status < 500 && typeof body?.detail === 'string' ? body.detail : null;
    throw Object.assign(new Error(detail ?? `La API respondió ${res.status}`), { unavailable: !detail });
  }
  return res.json();
}

// Varias secciones piden lo mismo (líneas, lugares, alertas): una sola petición por visita.
const cache = new Map();
function once(key, load) {
  if (!cache.has(key)) {
    cache.set(
      key,
      load().catch(err => {
        cache.delete(key);
        throw err;
      })
    );
  }
  return cache.get(key);
}

export const api = {
  // Sin `hora`/`dia` la API usa la hora actual del servidor (Bogotá).
  asistente: (texto, { hora, dia } = {}) =>
    request('/asistente', { method: 'POST', body: JSON.stringify({ texto, usar_directo: false, hora, dia }) }),
  capas: () => once('capas', () => request('/capas?incluir_zonas=false&incluir_alertas=false')),
  alertas: () => once('alertas', () => request('/alertas?activas=true&solo_vigentes=true')),
  lugares: () => once('lugares', () => request('/lugares')),
  health: () => once('health', () => request('/health')),
  tarifas: () => once('tarifas', () => request('/tarifas')),
  // Catálogo id -> línea.
  lineas: () => once('lineas', () => request('/lineas').then(r => new Map(r.lineas.map(l => [l.id, l])))),
  // Solo las líneas que pasan por Ciudad Bolívar: la API también trae rutas de prueba de otras
  // localidades (Suba, Usme, Kennedy, Bosa, Calle 80) que no se muestran ni se cuentan.
  lineasCB: () => api.lineas().then(m => new Map([...m].filter(([, l]) => passesThroughCB(l.geometria))))
};

export const passesThroughCB = geometria => (geometria?.coordinates ?? []).some(c => inCB(toLatLng(c)));
