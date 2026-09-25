import LogoLoop from './reactbits/LogoLoop';
import Icon from './Icon';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { modeLabel } from '../data/mapStyle';

const ICON_OF_MODO = { cable: 'cable', troncal: 'bus', sitp: 'bus', buseta: 'bus', colectivo: 'van', campero: 'van', mototaxi: 'moto' };
const CHANNELS = [
  { icon: 'chat', label: 'WhatsApp' },
  { icon: 'globe', label: 'App web' }
];

const toLogo = item => ({
  node: (
    <span className="mode-pill">
      <Icon name={item.icon} size={20} />
      {item.label}
    </span>
  ),
  ariaLabel: item.label
});

export default function ModesBand() {
  // Los modos salen de las líneas que tiene la API; los canales son del producto.
  const { data: lineas } = useApi(() => api.lineasCB());
  const modos = lineas ? [...new Set([...lineas.values()].map(l => l.modo))] : [];
  const items = [...modos.map(m => ({ icon: ICON_OF_MODO[m] ?? 'bus', label: modeLabel(m) })), ...CHANNELS];

  return (
    <section className="modes" aria-label="Sistemas integrados">
      <p className="modes__label">Todo el transporte de la localidad, en una sola respuesta</p>
      <LogoLoop
        logos={items.map(toLogo)}
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
