import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { gzipSync, constants } from 'node:zlib';

// Pre-comprime los archivos de texto para que nginx los sirva con gzip_static (nivel 9, sin costo por request).
const dist = new URL('../dist/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const TEXT = /\.(js|css|html|svg|json|txt|xml)$/;

let before = 0;
let after = 0;
function walk(dir) {
  for (const name of readdirSync(dir)) {
    const file = join(dir, name);
    if (statSync(file).isDirectory()) walk(file);
    else if (TEXT.test(name)) {
      const raw = readFileSync(file);
      if (raw.length < 1024) continue;
      const gz = gzipSync(raw, { level: constants.Z_BEST_COMPRESSION });
      writeFileSync(`${file}.gz`, gz);
      before += raw.length;
      after += gz.length;
    }
  }
}

walk(dist);
console.log(`Comprimido: ${(before / 1024).toFixed(0)} KB -> ${(after / 1024).toFixed(0)} KB (gzip -9)`);
