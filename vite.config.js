import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const VENDORS = [
  ['react', /[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/],
  ['gsap', /[\\/]node_modules[\\/](gsap|@gsap)[\\/]/],
  ['motion', /[\\/]node_modules[\\/](motion|framer-motion|motion-dom|motion-utils)[\\/]/]
];

export default defineConfig({
  plugins: [react()],
  build: {
    // Un solo CSS: las secciones diferidas llegan pre-renderadas y deben verse con estilo desde el primer pintado.
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          return VENDORS.find(([, re]) => re.test(id))?.[0];
        }
      }
    }
  }
});
