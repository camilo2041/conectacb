const GLYPHS = {
  accidente:
    '<path d="M5 17l1.6-5.2A2 2 0 0 1 8.5 10.4h7a2 2 0 0 1 1.9 1.4L19 17"/><path d="M4 17h16v2.5H4z"/><path d="M12 3v3M7.5 4.5l1.3 2M16.5 4.5l-1.3 2"/>',
  trancon: '<rect x="8.5" y="2.5" width="7" height="19" rx="3.5"/><circle cx="12" cy="7" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="12" cy="17" r="1.3"/>',
  desvio: '<path d="M6 21v-8a5 5 0 0 1 5-5h8"/><path d="M15.5 4.5L19 8l-3.5 3.5"/>',
  cierre: '<path d="M3 9h18v5H3z"/><path d="M7 9l3.5 5M12.5 9l3.5 5M6 14v6M18 14v6"/>',
  evento: '<path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.9l-5.4 2.6 1.2-6-4.5-4.2 6.1-.7z"/>'
};

export function eventIconSvg(type, size = 16) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${GLYPHS[type]}</svg>`;
}
