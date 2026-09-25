export const MODES = {
  walk: { label: 'Caminando', color: '#868ba8', icon: 'walk' },
  cable: { label: 'TransMiCable', color: '#ff5a3d', icon: 'cable' },
  sitp: { label: 'SITP', color: '#1f63ff', icon: 'bus' },
  troncal: { label: 'TransMilenio', color: '#d7263d', icon: 'bus' },
  colectivo: { label: 'Colectivo', color: '#12a150', icon: 'van' },
  veredal: { label: 'Ruta veredal', color: '#12a150', icon: 'van' }
};

export const PLACES = [
  'Mirador del Paraíso',
  'Manitas',
  'Juan Pablo II',
  'Portal Tunal',
  'Sierra Morena',
  'Arborizadora Alta',
  'Perdomo',
  'Lucero',
  'Jerusalén',
  'Quiba',
  'Mochuelo',
  'Centro'
];

export const TRIPS = [
  {
    from: 'Mirador del Paraíso',
    to: 'Portal Tunal',
    saved: 18,
    fare: 3200,
    legs: [
      { mode: 'walk', text: 'Camina a la estación Mirador del Paraíso', min: 3 },
      { mode: 'cable', text: 'TransMiCable directo hasta Portal Tunal', min: 13 }
    ]
  },
  {
    from: 'Sierra Morena',
    to: 'Centro',
    saved: 26,
    fare: 5700,
    legs: [
      { mode: 'walk', text: 'Camina al paradero de la Cra. 73', min: 4 },
      { mode: 'colectivo', text: 'Colectivo hasta Portal Sur', min: 17 },
      { mode: 'troncal', text: 'TransMilenio expreso hacia el Centro', min: 36 }
    ]
  },
  {
    from: 'Quiba',
    to: 'Portal Tunal',
    saved: 31,
    fare: 7200,
    alert: 'Derrumbe parcial en la vía a Quiba: la ruta veredal va por desvío, +9 min',
    legs: [
      { mode: 'veredal', text: 'Ruta veredal hasta Mirador del Paraíso', min: 24 },
      { mode: 'cable', text: 'TransMiCable hasta Portal Tunal', min: 13 }
    ]
  },
  {
    from: 'Arborizadora Alta',
    to: 'Perdomo',
    saved: 12,
    fare: 3200,
    legs: [
      { mode: 'walk', text: 'Camina al paradero Arborizadora Alta', min: 5 },
      { mode: 'sitp', text: 'SITP zonal hacia Perdomo', min: 21 },
      { mode: 'walk', text: 'Camina a tu destino', min: 3 }
    ]
  }
];

export const QUICK_TRIPS = TRIPS.map(t => `${t.from} a ${t.to}`);

const normalize = s =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');

function findPlaces(query) {
  const q = normalize(query);
  return PLACES.map(p => ({ p, i: q.indexOf(normalize(p)) }))
    .filter(x => x.i >= 0)
    .sort((a, b) => a.i - b.i)
    .map(x => x.p);
}

export function planTrip(query) {
  const found = findPlaces(query);
  if (found.length < 2) return null;
  const [from, to] = found;

  const direct = TRIPS.find(t => t.from === from && t.to === to);
  if (direct) return direct;

  const reversed = TRIPS.find(t => t.from === to && t.to === from);
  if (reversed) {
    return {
      ...reversed,
      from,
      to,
      alert: undefined,
      legs: [...reversed.legs].reverse().map((l, i, arr) => ({
        ...l,
        text:
          l.mode === 'walk'
            ? i === arr.length - 1
              ? `Camina hasta ${to}`
              : 'Camina a tu primera conexión'
            : `${MODES[l.mode].label} ${i === arr.length - 1 ? `hasta ${to}` : 'hasta tu siguiente conexión'}`
      }))
    };
  }

  return {
    from,
    to,
    saved: 15,
    fare: 5700,
    legs: [
      { mode: 'walk', text: `Camina al paradero más cercano en ${from}`, min: 4 },
      { mode: 'colectivo', text: 'Colectivo hasta la estación Juan Pablo II', min: 12 },
      { mode: 'cable', text: 'TransMiCable hasta Portal Tunal', min: 9 },
      { mode: 'sitp', text: `SITP hacia ${to}`, min: 18 }
    ]
  };
}
