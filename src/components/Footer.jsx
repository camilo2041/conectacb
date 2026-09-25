import badge from '../assets/badge-80.webp';
import Icon from './Icon';
import { WHATSAPP_DISPLAY, WHATSAPP_URL } from '../config';

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer__inner">
        <a href="#top" className="nav__brand" aria-label="ConectaCB, volver arriba">
          <img src={badge} alt="" width="40" height="40" loading="lazy" decoding="async" />
          <span className="nav__word">
            Conecta<b className="text-brand">CB</b>
          </span>
        </a>
        <nav className="footer__links" aria-label="Pie de página">
          <a href="#planear">Planear ruta</a>
          <a href="#mapa">Mapa</a>
          <a href="#beneficios">Beneficios</a>
          <a href="#como-funciona">Cómo funciona</a>
          <a href="#app">App</a>
        </nav>
        <a href={WHATSAPP_URL} target="_blank" rel="noreferrer" className="footer__wa">
          <Icon name="chat" size={18} /> {WHATSAPP_DISPLAY}
        </a>
        <span className="footer__copy" suppressHydrationWarning>
          © {new Date().getFullYear()} ConectaCB · Movilidad integrada con IA
        </span>
      </div>
    </footer>
  );
}
