import { useEffect, useState } from 'react';
import Magnet from './reactbits/Magnet';
import Icon from './Icon';
import badge from '../assets/badge.png';

const LINKS = [
  { href: '#planear', label: 'Planear ruta' },
  { href: '#mapa', label: 'Mapa' },
  { href: '#beneficios', label: 'Beneficios' },
  { href: '#como-funciona', label: 'Cómo funciona' },
  { href: '#app', label: 'App' }
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header className={`nav ${scrolled || open ? 'nav--solid' : ''}`}>
      <div className="container nav__inner">
        <a href="#top" className="nav__brand" aria-label="ConectaCB, inicio">
          <img src={badge} alt="" width="40" height="40" />
          <span className="nav__word">
            Conecta<b className="text-brand">CB</b>
          </span>
        </a>

        <nav className={`nav__links ${open ? 'is-open' : ''}`} aria-label="Principal">
          {LINKS.map(l => (
            <a key={l.href} href={l.href} onClick={() => setOpen(false)}>
              {l.label}
            </a>
          ))}
        </nav>

        <div className="nav__actions">
          <Magnet padding={40} magnetStrength={4}>
            <a href="#planear" className="btn btn-brand nav__cta">
              Probar gratis
            </a>
          </Magnet>
          <button
            className="nav__toggle"
            aria-label={open ? 'Cerrar menú' : 'Abrir menú'}
            aria-expanded={open}
            onClick={() => setOpen(o => !o)}
          >
            <Icon name={open ? 'close' : 'menu'} />
          </button>
        </div>
      </div>
    </header>
  );
}
