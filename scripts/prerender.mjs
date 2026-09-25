import { readFileSync, rmSync, writeFileSync } from 'node:fs';

const distIndex = new URL('../dist/index.html', import.meta.url);
const ssrDir = new URL('../dist-ssr/', import.meta.url);

const { render } = await import(new URL('entry-server.js', ssrDir).href);
const template = readFileSync(distIndex, 'utf8');

if (!template.includes('<!--app-html-->')) throw new Error('dist/index.html no tiene el marcador <!--app-html-->');

const html = await render();
writeFileSync(distIndex, template.replace('<!--app-html-->', html));
rmSync(ssrDir, { recursive: true, force: true });

console.log(`Pre-renderizado: ${(html.length / 1024).toFixed(1)} KB de HTML en dist/index.html`);
