// La API guarda los nombres sin tildes; se corrigen solo para mostrarlos.
const ACCENTS = [
  [/\bParaiso\b/g, 'Paraíso'],
  [/\bCazuca\b/g, 'Cazucá'],
  [/\bEstacion\b/g, 'Estación'],
  [/\bestacion\b/g, 'estación'],
  [/\bVia\b/g, 'Vía'],
  [/\bvia\b/g, 'vía'],
  [/\bBolivar\b/g, 'Bolívar'],
  [/\bTrafico\b/g, 'Tráfico'],
  [/\btrafico\b/g, 'tráfico'],
  [/\bDesvio\b/g, 'Desvío'],
  [/\bdesvio\b/g, 'desvío'],
  [/\bencontre\b/g, 'encontré']
];

export const accent = text => ACCENTS.reduce((t, [re, fix]) => t.replace(re, fix), text ?? '');

export const money = n => `$${String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.')}`;
