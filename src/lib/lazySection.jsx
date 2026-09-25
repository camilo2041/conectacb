import { lazy } from 'react';

const isServer = typeof window === 'undefined';
const loaders = new Map();
const loaded = new Map();

function whenNear(anchorId) {
  return new Promise(resolve => {
    const el = document.getElementById(anchorId);
    if (!el || !('IntersectionObserver' in window)) return resolve();
    const io = new IntersectionObserver(
      entries => {
        if (entries.some(e => e.isIntersecting)) {
          io.disconnect();
          resolve();
        }
      },
      { rootMargin: '600px 0px' }
    );
    io.observe(el);
  });
}

// Sección que se hidrata al acercarse a la pantalla. Mientras tanto React conserva el HTML
// pre-renderado (visible) sin descargar ni ejecutar su JavaScript.
// En el servidor se renderiza directo (tras preloadSections) para que el HTML salga completo y en orden.
export function lazySection(anchorId, loader) {
  loaders.set(anchorId, loader);
  if (!isServer) return lazy(() => whenNear(anchorId).then(loader));

  function ServerSection(props) {
    const Component = loaded.get(anchorId);
    return <Component {...props} />;
  }
  return ServerSection;
}

export async function preloadSections() {
  await Promise.all([...loaders].map(async ([id, loader]) => loaded.set(id, (await loader()).default)));
}
