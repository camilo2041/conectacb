import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import SplitText from './reactbits/SplitText';
import ShinyText from './reactbits/ShinyText';
import Icon from './Icon';
import { api } from '../lib/api';
import { routeStore } from '../lib/routeStore';
import { accent, money } from '../lib/text';
import { SYSTEMS, WALK_COLOR, modeLabel } from '../data/mapStyle';

const EXAMPLES = [
  { label: 'Cazucá a Juan Pablo II', query: 'de Cazuca a Juan Pablo II' },
  { label: 'Arborizadora Alta a Las Aguas', query: 'de Arborizadora Alta a Las Aguas' },
  { label: 'Quiba a Portal Tunal', query: 'de Quiba a Portal Tunal' },
  { label: 'Bella Flor a Portal Tunal', query: 'de Bella Flor a Portal Tunal' }
];

const LEG_STYLE = {
  walk: { color: WALK_COLOR, icon: 'walk' },
  cable: { color: SYSTEMS.cable.color, icon: 'cable' },
  formal: { color: SYSTEMS.formal.color, icon: 'bus' },
  informal: { color: SYSTEMS.informal.color, icon: 'van' }
};

// La API necesita "de X a Y" para saber cuál es el origen.
function toQuestion(text) {
  const t = text.trim();
  if (/\b(de|desde)\s/i.test(t) || /^(c[oó]mo|quiero|necesito|voy)\b/i.test(t)) return t;
  return `de ${t}`;
}

// "TransMiCable Tunal (Portal Tunal - Mirador del Paraiso)" -> "Portal Tunal - Mirador del Paraiso"
const lineRoute = nombre =>
  nombre.match(/\(([^)]+)\)/)?.[1] ?? nombre.replace(/^(troncal\s+)?(transmicable|transmilenio|colectivo|buseta|campero|mototaxi)\s+/i, '');

function toView(resp, lineas) {
  const r = resp.ruta;
  if (!r?.tramos?.length) return null;

  const legs = [];
  for (const t of r.tramos) {
    if (t.modo === 'directo') continue;
    if (t.modo === 'acceso') {
      const min = Math.round(t.duracion_seg / 60);
      if (min >= 1) legs.push({ kind: 'walk', label: 'Caminando', text: `${Math.round(t.distancia_m)} m`, min });
      continue;
    }
    const linea = lineas.get(t.linea);
    const label = modeLabel(linea?.modo ?? t.modo);
    legs.push({
      kind: t.modo === 'cable' ? 'cable' : t.modo === 'informal' ? 'informal' : 'formal',
      label: `${label} · ${t.linea}`,
      text: accent(linea ? lineRoute(linea.nombre) : t.linea),
      min: Math.max(1, Math.round(t.duracion_seg / 60))
    });
  }

  return {
    key: resp.texto,
    from: accent(resp.origen?.nombre ?? 'Origen'),
    to: accent(resp.destino?.nombre ?? 'Destino'),
    minutes: Math.max(1, Math.round(r.duracion_seg / 60)),
    fare: r.tarifa_total_cop,
    transfers: r.transbordos,
    legs,
    novedades: r.novedades ?? [],
    tramos: r.tramos,
    origen: resp.origen,
    destino: resp.destino
  };
}

function arrivalTime(now, minutes) {
  return new Date(now + minutes * 60000).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });
}

export default function Planner() {
  const [query, setQuery] = useState(EXAMPLES[0].label);
  const [status, setStatus] = useState('thinking');
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState('');
  // La hora se toma en el navegador; el HTML pre-renderado no puede saberla.
  const [now, setNow] = useState(null);
  const lastRequest = useRef(0);

  const run = async (text = query) => {
    const id = ++lastRequest.current;
    setStatus('thinking');
    try {
      const [resp, lineas] = await Promise.all([api.asistente(toQuestion(text)), api.lineas()]);
      if (id !== lastRequest.current) return;
      const view = toView(resp, lineas);
      setNow(Date.now());
      setResult(view);
      setMessage(view ? '' : accent(resp.respuesta));
      setStatus(view ? 'done' : 'empty');
    } catch (err) {
      if (id !== lastRequest.current) return;
      setMessage(
        err instanceof TypeError || err.unavailable
          ? 'El asistente no está disponible en este momento. Intenta de nuevo en unos minutos.'
          : accent(err.message)
      );
      setStatus('error');
    }
  };

  useEffect(() => {
    run(EXAMPLES[0].query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pickExample = ex => {
    setQuery(ex.label);
    run(ex.query);
  };

  const showOnMap = () => {
    routeStore.set(result);
    document.getElementById('mapa')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section className="section planner" id="planear">
      <div className="container planner__grid">
        <div className="planner__copy">
          <span className="eyebrow">
            <span className="eyebrow-dot" />
            <ShinyText text="Asistente con IA" color="#474c6b" shineColor="#1f63ff" speed={3} />
          </span>
          <SplitText
            text="¿A dónde vas hoy?"
            tag="h2"
            className="display h2"
            textAlign="left"
            splitType="chars"
            delay={35}
            duration={0.9}
            from={{ opacity: 0, y: 50 }}
            to={{ opacity: 1, y: 0 }}
          />
          <p className="lead">Dinos de dónde sales y a dónde vas. ConectaCB combina TransMiCable, SITP, colectivos y rutas veredales para darte la ruta más rápida.</p>

          <div className="chips">
            {EXAMPLES.map(ex => (
              <button key={ex.label} type="button" className={`chip ${ex.label === query ? 'is-active' : ''}`} onClick={() => pickExample(ex)}>
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        <div className="planner__card">
          <form
            className="ask"
            onSubmit={e => {
              e.preventDefault();
              if (query.trim()) run();
            }}
          >
            <Icon name="pin" size={20} className="ask__icon" />
            <label htmlFor="trip-query" className="sr-only">
              Origen y destino
            </label>
            <input
              id="trip-query"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Ej: Manitas a Portal Tunal"
              autoComplete="off"
            />
            <button type="submit" className="ask__send" aria-label="Buscar ruta">
              <Icon name="send" size={18} />
            </button>
          </form>

          <div className="answer" aria-live="polite">
            <AnimatePresence mode="wait">
              {status === 'thinking' && (
                <motion.div key="thinking" className="thinking" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <span className="thinking__dots">
                    <i />
                    <i />
                    <i />
                  </span>
                  Revisando TransMiCable, SITP y rutas informales…
                </motion.div>
              )}

              {(status === 'empty' || status === 'error') && (
                <motion.div key="msg" className="notfound" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                  <p>{message}</p>
                  {status === 'empty' && !/prueba/i.test(message) && (
                    <p>
                      Prueba con barrios, veredas o estaciones de la localidad, por ejemplo <b>Lucero a Portal Tunal</b>.
                    </p>
                  )}
                </motion.div>
              )}

              {status === 'done' && result && (
                <motion.div
                  key={result.key}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.45, ease: [0.2, 0.8, 0.2, 1] }}
                >
                  <div className="answer__head">
                    <div>
                      <span className="answer__route">
                        {result.from} <Icon name="arrow" size={14} /> {result.to}
                      </span>
                      <div className="answer__time">
                        <strong>{result.minutes}</strong> min
                      </div>
                    </div>
                    <div className="answer__meta">
                      {now && (
                        <span>
                          <Icon name="clock" size={16} /> Llegas {arrivalTime(now, result.minutes)}
                        </span>
                      )}
                      <span>
                        <Icon name="coin" size={16} /> {money(result.fare)}
                      </span>
                      <span className="answer__saved">
                        {result.transfers === 0 ? 'Sin transbordos' : `${result.transfers} transbordo${result.transfers > 1 ? 's' : ''}`}
                      </span>
                    </div>
                  </div>

                  <ol className="legs">
                    {result.legs.map((l, i) => {
                      const s = LEG_STYLE[l.kind];
                      return (
                        <motion.li
                          key={i}
                          className="leg"
                          style={{ '--mode': s.color }}
                          initial={{ opacity: 0, x: -12 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.12 + i * 0.12 }}
                        >
                          <span className="leg__icon">
                            <Icon name={s.icon} size={18} />
                          </span>
                          <span className="leg__body">
                            <b>{l.label}</b>
                            <span>{l.text}</span>
                          </span>
                          <span className="leg__min">{l.min} min</span>
                        </motion.li>
                      );
                    })}
                  </ol>

                  {result.novedades.map(n => (
                    <div className="answer__alert" key={n.id}>
                      <Icon name="alert" size={16} /> {accent(n.titulo)}
                      {n.retraso_seg > 0 && ` · +${Math.round(n.retraso_seg / 60)} min`}
                    </div>
                  ))}

                  <button type="button" className="answer__map" onClick={showOnMap}>
                    <Icon name="pin" size={16} /> Ver ruta en el mapa
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  );
}
