import { StrictMode } from 'react';
import { createRoot, hydrateRoot } from 'react-dom/client';
import '@fontsource-variable/jost';
import './styles/index.css';
import App from './App.jsx';

const container = document.getElementById('root');
const app = (
  <StrictMode>
    <App />
  </StrictMode>
);

// En producción el HTML viene pre-renderado (scripts/prerender.mjs); en desarrollo llega vacío.
if (container.firstElementChild) hydrateRoot(container, app);
else createRoot(container).render(app);
