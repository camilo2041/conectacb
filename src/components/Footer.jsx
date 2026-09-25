import badge from '../assets/badge.png';

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer__inner">
        <a href="#top" className="nav__brand" aria-label="ConectaCB, volver arriba">
          <img src={badge} alt="" width="40" height="40" />
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
        <span className="footer__copy">© {new Date().getFullYear()} ConectaCB · Movilidad integrada con IA</span>
      </div>
    </footer>
  );
}
