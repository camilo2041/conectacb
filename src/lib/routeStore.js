// Ruta elegida en el planeador para dibujarla en el mapa. Vive fuera de React porque ambas
// secciones se cargan por separado y el mapa puede montarse después de que se eligió la ruta.
let current = null;
const listeners = new Set();

export const routeStore = {
  get: () => current,
  set(route) {
    current = route;
    listeners.forEach(fn => fn(route));
  },
  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }
};
