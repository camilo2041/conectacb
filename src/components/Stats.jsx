import CountUp from './reactbits/CountUp';

const STATS = [
  { to: 5, suffix: '', label: 'sistemas de transporte en un solo chat' },
  { to: 120, suffix: '+', label: 'rutas y paraderos mapeados' },
  { to: 24, suffix: '/7', label: 'disponible, también de madrugada' },
  { to: 9, from: 0, down: true, suffix: '', label: 'apps que descargar' }
];

export default function Stats() {
  return (
    <section className="stats" id="cifras" aria-label="ConectaCB en cifras">
      <div className="container stats__grid">
        {STATS.map(s => (
          <div className="stat" key={s.label}>
            <div className="stat__num display">
              <CountUp to={s.to} from={s.from ?? 0} direction={s.down ? 'down' : 'up'} duration={2} />
              <span>{s.suffix}</span>
            </div>
            <p>{s.label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
