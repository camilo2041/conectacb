// Convenciones visuales del mapa y del planeador, según los tipos que devuelve la API.

export const SYSTEMS = {
  cable: { label: 'TransMiCable', color: '#ff5a3d', style: 'solid', desc: 'Cable aéreo Línea 1 · 4 estaciones' },
  formal: { label: 'TransMilenio y SITP', color: '#1f63ff', style: 'dash', desc: 'Troncales, zonales y alimentadores' },
  informal: { label: 'Informales', color: '#12a150', style: 'dot', desc: 'Colectivos, busetas, camperos y mototaxis' }
};

export const WALK_COLOR = '#868ba8';

export const systemOf = tipo => (tipo === 'cable' ? 'cable' : tipo === 'informal' ? 'informal' : 'formal');

const MODE_LABELS = {
  cable: 'TransMiCable',
  troncal: 'TransMilenio',
  sitp: 'SITP',
  colectivo: 'Colectivo',
  buseta: 'Buseta',
  campero: 'Campero',
  mototaxi: 'Mototaxi'
};

export const modeLabel = modo => MODE_LABELS[modo] ?? (modo ? modo[0].toUpperCase() + modo.slice(1) : 'Transporte');

export const EVENT_TYPES = {
  derrumbe: { label: 'Derrumbe', color: '#92400e', desc: 'Tierra o rocas sobre la vía; puede cerrar el paso' },
  obra: { label: 'Obra', color: '#ea580c', desc: 'Trabajos en la vía que cambian el recorrido' },
  bloqueo: { label: 'Bloqueo', color: '#e11d48', desc: 'Vía cerrada por un incidente o una protesta' },
  trafico: { label: 'Trancón', color: '#f59e0b', desc: 'Tráfico lento: los viajes por la zona tardan más' },
  desvio: { label: 'Desvío', color: '#7a3cff', desc: 'La ruta toma un recorrido alterno' },
  clima: { label: 'Clima', color: '#0891b2', desc: 'Lluvia o granizo que retrasa los viajes' },
  otro: { label: 'Otra novedad', color: '#475569', desc: 'Reportes de la comunidad' }
};

export const eventType = tipo => EVENT_TYPES[tipo] ?? EVENT_TYPES.otro;

// Recuadro de Ciudad Bolívar: el mapa se encuadra aquí aunque la API traiga líneas de otras localidades.
export const CB_BOUNDS = { south: 4.49, north: 4.6, west: -74.21, east: -74.12 };

export const inCB = ({ lat, lng }) =>
  lat >= CB_BOUNDS.south && lat <= CB_BOUNDS.north && lng >= CB_BOUNDS.west && lng <= CB_BOUNDS.east;

export const toLatLng = ([lng, lat]) => ({ lat, lng });
