import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const VENDORS = [
  ['react', /[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/],
  ['gsap', /[\\/]node_modules[\\/](gsap|@gsap)[\\/]/],
  ['motion', /[\\/]node_modules[\\/](motion|framer-motion|motion-dom|motion-utils)[\\/]/]
];

// En desarrollo /api va a la API local (uvicorn en :8000); en producción lo reenvía nginx.
const apiProxy = {
  '/api': {
    target: process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000',
    changeOrigin: true,
    rewrite: path => path.replace(/^\/api/, '')
  }
};

export default defineConfig({
  plugins: [react()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
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
