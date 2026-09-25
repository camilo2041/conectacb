import CardSwap, { Card } from './reactbits/CardSwap';
import SplitText from './reactbits/SplitText';
import Icon from './Icon';
import { api } from '../lib/api';
import { SAMPLE_TRIP, useApi } from '../lib/useApi';
import { accent, lineRoute, money } from '../lib/text';
import { SYSTEMS, modeLabel } from '../data/mapStyle';

const STEPS = [
  { title: 'Escribe tu destino', text: 'Por WhatsApp o en la web, con tus propias palabras.' },
  { title: 'El asistente combina todo', text: 'Horarios de TransMiCable, TransMilenio y rutas informales en una sola búsqueda.' },
  { title: 'Sal a la hora justa', text: 'Recibe tu ruta, tu tarifa y las novedades que la afectan.' }
];

const SYSTEM_OF_MODO = { cable: 'cable', informal: 'informal', formal: 'formal' };

function toCards(resp, lineas) {
  const r = resp.ruta;
  if (!r?.tramos?.length) return null;
  const legs = r.tramos
    .filter(t => t.modo !== 'acceso' && t.modo !== 'directo')
    .map(t => ({ linea: lineas.get(t.linea), system: SYSTEM_OF_MODO[t.modo], min: Math.max(1, Math.round(t.duracion_seg / 60)) }));
  const minutes = Math.max(1, Math.round(r.duracion_seg / 60));
  const [h, m] = SAMPLE_TRIP.hora.split(':').map(Number);
  const hora = extra => new Date(2000, 0, 1, h, m + extra).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });
  const [llegada, ...meridiano] = hora(minutes).split(' ');
  return { legs, minutes, llegada, meridiano: meridiano.join(' '), salida: hora(0), fare: r.tarifa_total_cop, novedad: r.novedades[0], first: legs[0]?.linea };
}

function Screen({ icon, title, tag, children }) {
  return (
    <>
      <div className="screen__bar">
        <span className="screen__dots">
          <i />
          <i />
          <i />
        </span>
        <span className="screen__title">
          <Icon name={icon} size={15} /> {title}
        </span>
        {tag && <span className="screen__tag">{tag}</span>}
      </div>
      <div className="screen__body">{children}</div>
    </>
  );
}

const Loading = () => <span className="screen__muted">Calculando con la API…</span>;

export default function HowItWorks() {
  const { data } = useApi(() => Promise.all([api.asistente(SAMPLE_TRIP.texto, SAMPLE_TRIP), api.lineas()]));
  const c = data && toCards(...data);

  return (
    <section className="section how" id="como-funciona">
      <div className="container how__grid">
        <div className="how__copy">
          <span className="eyebrow">
            <span className="eyebrow-dot" /> Cómo funciona
          </span>
          <SplitText
            text="Tres pasos. Cero adivinanzas."
            tag="h2"
            className="display h2"
            textAlign="left"
            splitType="words"
            delay={90}
            duration={1}
            from={{ opacity: 0, y: 40 }}
            to={{ opacity: 1, y: 0 }}
          />
          <ol className="steps">
            {STEPS.map((s, i) => (
              <li key={s.title} className="step">
                <span className="step__num">{String(i + 1).padStart(2, '0')}</span>
                <div>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </div>
              </li>
            ))}
          </ol>
          <p className="how__sample">
            <Icon name="route" size={16} /> Las tarjetas muestran un viaje real calculado por la API: {SAMPLE_TRIP.label}
          </p>
        </div>

        <div className="swap-stage" aria-hidden="true">
          <CardSwap width={380} height={290} cardDistance={48} verticalDistance={56} delay={4200} pauseOnHover skewAmount={4}>
            <Card customClass="screen">
              <Screen icon="route" title="Ruta sugerida" tag="Más rápida">
                {c ? (
                  <>
                    <div className="screen__big">
                      {c.minutes} <small>min</small>
                    </div>
                    <div className="screen__legs">
                      {c.legs.map((l, i) => (
                        <span key={i} style={{ '--c': SYSTEMS[l.system].color }}>
                          {modeLabel(l.linea?.modo)} {l.min}′
                        </span>
                      ))}
                    </div>
                  </>
                ) : (
                  <Loading />
                )}
              </Screen>
            </Card>
            <Card customClass="screen">
              <Screen icon="pin" title="Primera línea">
                {c?.first ? (
                  <>
                    <div className="screen__row">
                      <b>{accent(lineRoute(c.first.nombre))}</b>
                      <span>
                        {modeLabel(c.first.modo)}
                        {c.first.frecuencia_min && ` · pasa cada ${c.first.frecuencia_min} min`}
                      </span>
                    </div>
                    <div className="screen__row">
                      <b>Horario</b>
                      <span>
                        {c.first.horario.ini} a {c.first.horario.fin}
                      </span>
                    </div>
                  </>
                ) : (
                  <Loading />
                )}
              </Screen>
            </Card>
            <Card customClass="screen">
              <Screen icon="alert" title="Novedad en tu ruta">
                {!c && <Loading />}
                {c?.novedad && (
                  <>
                    <div className="screen__alert">{accent(c.novedad.titulo)}</div>
                    <div className="screen__row">
                      <b>+{Math.round(c.novedad.retraso_seg / 60)} min</b>
                      <span>ya sumados al tiempo total del viaje</span>
                    </div>
                  </>
                )}
                {c && !c.novedad && (
                  <div className="screen__row">
                    <b>Sin novedades</b>
                    <span>Ninguna alerta activa afecta esta ruta</span>
                  </div>
                )}
              </Screen>
            </Card>
            <Card customClass="screen">
              <Screen icon="clock" title="Llegada estimada">
                {c ? (
                  <>
                    <div className="screen__big">
                      {c.llegada} <small>{c.meridiano}</small>
                    </div>
                    <div className="screen__progress">
                      <i />
                    </div>
                    <span className="screen__muted">
                      Saliendo a las {c.salida} · {money(c.fare)}
                    </span>
                  </>
                ) : (
                  <Loading />
                )}
              </Screen>
            </Card>
          </CardSwap>
        </div>
      </div>
    </section>
  );
}
