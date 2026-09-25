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

let lineasPromise;

export const api = {
  asistente: texto => request('/asistente', { method: 'POST', body: JSON.stringify({ texto, usar_directo: false }) }),
  capas: () => request('/capas?incluir_zonas=false&incluir_alertas=false'),
  alertas: () => request('/alertas?activas=true&solo_vigentes=true'),
  lugares: () => request('/lugares'),
  // Catálogo id -> línea; se pide una sola vez por visita.
  lineas() {
    lineasPromise ??= request('/lineas')
      .then(r => new Map(r.lineas.map(l => [l.id, l])))
      .catch(err => {
        lineasPromise = undefined;
        throw err;
      });
    return lineasPromise;
  }
};
