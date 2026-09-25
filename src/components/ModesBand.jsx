import LogoLoop from './reactbits/LogoLoop';
import Icon from './Icon';

const ITEMS = [
  { icon: 'cable', label: 'TransMiCable' },
  { icon: 'bus', label: 'SITP' },
  { icon: 'bus', label: 'TransMilenio' },
  { icon: 'van', label: 'Colectivos' },
  { icon: 'van', label: 'Rutas veredales' },
  { icon: 'walk', label: 'Tramos a pie' },
  { icon: 'chat', label: 'WhatsApp' },
  { icon: 'globe', label: 'App web' }
];

const logos = ITEMS.map(i => ({
  node: (
    <span className="mode-pill">
      <Icon name={i.icon} size={20} />
      {i.label}
    </span>
  ),
  ariaLabel: i.label
}));

export default function ModesBand() {
  return (
    <section className="modes" aria-label="Sistemas integrados">
      <p className="modes__label">Todo el transporte de la localidad, en una sola respuesta</p>
      <LogoLoop
        logos={logos}
        speed={60}
        direction="left"
        logoHeight={44}
        gap={18}
        pauseOnHover
        fadeOut
        fadeOutColor="#0b0c22"
        ariaLabel="Sistemas de transporte integrados"
      />
    </section>
  );
}
