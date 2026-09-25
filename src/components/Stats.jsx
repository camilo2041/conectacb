import CountUp from './reactbits/CountUp';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';

export default function Stats() {
  const { data } = useApi(() => Promise.all([api.health(), api.lineas(), api.alertas()]));

  let stats = [
    { label: 'rutas integradas en el planeador' },
    { label: 'estaciones de TransMiCable' },
    { label: 'barrios, veredas y estaciones que el asistente reconoce' },
    { label: 'novedades activas reportadas' }
  ];
  if (data) {
    const [health, lineas, alertas] = data;
    const estaciones = [...lineas.values()].filter(l => l.tipo === 'cable').reduce((s, l) => s + l.num_paradas, 0);
    const valores = [health.rutas_formales + health.rutas_informales, estaciones, health.lugares, alertas.length];
    stats = stats.map((s, i) => ({ ...s, value: valores[i] }));
  }

  return (
    <section className="stats" id="cifras" aria-label="ConectaCB en cifras">
      <div className="container stats__grid">
        {stats.map(s => (
          <div className="stat" key={s.label}>
            <div className="stat__num display">{s.value === undefined ? '–' : <CountUp to={s.value} duration={1.6} />}</div>
            <p>{s.label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
