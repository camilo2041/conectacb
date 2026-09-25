const GLYPHS = {
  derrumbe: '<path d="M3 20l6-10 4 6 2-3 6 7z"/><circle cx="16" cy="6" r="1.6"/><circle cx="12.5" cy="4.5" r="1"/>',
  obra: '<path d="M10 3h4l4.5 16h-13z"/><path d="M8.2 11h7.6M7 15.5h10M3.5 21h17"/>',
  bloqueo: '<path d="M3 9h18v5H3z"/><path d="M7 9l3.5 5M12.5 9l3.5 5M6 14v6M18 14v6"/>',
  trafico: '<rect x="8.5" y="2.5" width="7" height="19" rx="3.5"/><circle cx="12" cy="7" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="12" cy="17" r="1.3"/>',
  desvio: '<path d="M6 21v-8a5 5 0 0 1 5-5h8"/><path d="M15.5 4.5L19 8l-3.5 3.5"/>',
  clima: '<path d="M7 15a4 4 0 1 1 .8-7.9A5.5 5.5 0 0 1 18.5 9 3.5 3.5 0 0 1 18 16H7"/><path d="M9 19l-1 2M13 19l-1 2M17 19l-1 2"/>',
  otro: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.1"/>'
};

export function eventIconSvg(tipo, size = 16) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${GLYPHS[tipo] ?? GLYPHS.otro}</svg>`;
}
