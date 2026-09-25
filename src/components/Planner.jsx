import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import SplitText from './reactbits/SplitText';
import ShinyText from './reactbits/ShinyText';
import Icon from './Icon';
import { MODES, QUICK_TRIPS, planTrip } from '../data/trips';

const money = n => `$${n.toLocaleString('es-CO')}`;

function arrivalTime(minutes) {
  const d = new Date(Date.now() + minutes * 60000);
  return d.toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });
}

export default function Planner() {
  const [query, setQuery] = useState(QUICK_TRIPS[2]);
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(() => planTrip(QUICK_TRIPS[2]));
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const run = text => {
    const q = text ?? query;
    if (text) setQuery(text);
    clearTimeout(timer.current);
    setStatus('thinking');
    timer.current = setTimeout(() => {
      const plan = planTrip(q);
      setResult(plan);
      setStatus(plan ? 'done' : 'notfound');
    }, 900);
  };

  const total = result ? result.legs.reduce((s, l) => s + l.min, 0) : 0;

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
            {QUICK_TRIPS.map(t => (
              <button key={t} type="button" className={`chip ${t === query ? 'is-active' : ''}`} onClick={() => run(t)}>
                {t}
              </button>
            ))}
          </div>
        </div>

        <div className="planner__card">
          <form
            className="ask"
            onSubmit={e => {
              e.preventDefault();
              run();
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
                <motion.div
                  key="thinking"
                  className="thinking"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <span className="thinking__dots">
                    <i />
                    <i />
                    <i />
                  </span>
                  Revisando TransMiCable, SITP y rutas informales…
                </motion.div>
              )}

              {status === 'notfound' && (
                <motion.div key="nf" className="notfound" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                  Prueba con dos lugares de la localidad, por ejemplo <b>Lucero a Centro</b>.
                </motion.div>
              )}

              {(status === 'done' || status === 'idle') && result && (
                <motion.div
                  key={result.from + result.to}
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
                        <strong>{total}</strong> min
                      </div>
                    </div>
                    <div className="answer__meta">
                      <span>
                        <Icon name="clock" size={16} /> Llegas {arrivalTime(total)}
                      </span>
                      <span>
                        <Icon name="coin" size={16} /> {money(result.fare)}
                      </span>
                      <span className="answer__saved">−{result.saved} min vs. ruta habitual</span>
                    </div>
                  </div>

                  <ol className="legs">
                    {result.legs.map((l, i) => {
                      const m = MODES[l.mode];
                      return (
                        <motion.li
                          key={i}
                          className="leg"
                          style={{ '--mode': m.color }}
                          initial={{ opacity: 0, x: -12 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.12 + i * 0.12 }}
                        >
                          <span className="leg__icon">
                            <Icon name={m.icon} size={18} />
                          </span>
                          <span className="leg__body">
                            <b>{m.label}</b>
                            <span>{l.text}</span>
                          </span>
                          <span className="leg__min">{l.min} min</span>
                        </motion.li>
                      );
                    })}
                  </ol>

                  {result.alert && (
                    <div className="answer__alert">
                      <Icon name="alert" size={16} /> {result.alert}
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  );
}
