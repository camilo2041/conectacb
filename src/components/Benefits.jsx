import SpotlightCard from './reactbits/SpotlightCard';
import BlurText from './reactbits/BlurText';
import Icon from './Icon';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { accent, money } from '../lib/text';
import { SYSTEMS, modeLabel } from '../data/mapStyle';

const PREGUNTA = { texto: 'de Manitas a Portal Tunal', hora: '07:00', dia: 'L' };
const SEVERIDAD = { alta: 'crit', media: 'warn', baja: 'ok' };

// La respuesta del asistente trae la tarifa con coma de miles ("$3,200"): se muestra en formato colombiano.
const formatoPesos = texto => texto.replace(/\$([\d,]+)/g, (_, n) => money(Number(n.replace(/,/g, ''))));

function rango(tarifas) {
  const min = Math.min(...tarifas);
  const max = Math.max(...tarifas);
  return min === max ? money(min) : `${money(min)} a ${money(max)}`;
}

export default function Benefits() {
  const chat = useApi(() => api.asistente(PREGUNTA.texto, PREGUNTA));
  const alertas = useApi(() => api.alertas());
  const tarifas = useApi(() => api.tarifas());

  const t = tarifas.data;
  const integradas = t?.lineas.filter(l => l.integrado) ?? [];
  const informales = t?.lineas.filter(l => !l.integrado) ?? [];

  return (
    <section className="section" id="beneficios">
      <div className="container">
        <div className="section-head center">
          <span className="eyebrow">
            <span className="eyebrow-dot" /> Beneficios
          </span>
          <BlurText as="h2" text="Menos espera. Más ciudad." className="display h2 blur-center" delay={120} animateBy="words" direction="top" />
        </div>

        <div className="bento">
          <SpotlightCard className="tile tile--night" spotlightColor="rgba(20, 195, 242, 0.25)">
            <span className="tile__icon">
              <Icon name="chat" />
            </span>
            <h3>En WhatsApp</h3>
            <p>Sin descargar nada. Escribe como le escribes a un amigo.</p>
            <div className="bubbles">
              <span className="bubble bubble--me">¿Cómo llego de Manitas a Portal Tunal?</span>
              {chat.data ? (
                <span className="bubble">{formatoPesos(accent(chat.data.respuesta))}</span>
              ) : (
                <span className="bubble bubble--typing" aria-label={chat.error ? 'El asistente no está disponible' : 'Escribiendo'}>
                  <i />
                  <i />
                  <i />
                </span>
              )}
            </div>
          </SpotlightCard>

          <SpotlightCard className="tile" spotlightColor="rgba(122, 60, 255, 0.14)">
            <span className="tile__icon">
              <Icon name="route" />
            </span>
            <h3>Una sola ruta</h3>
            <p>Formal e informal combinados en la misma recomendación.</p>
            <div className="mode-dots">
              {Object.values(SYSTEMS).map(s => (
                <i key={s.color} style={{ background: s.color }} title={s.label} />
              ))}
            </div>
          </SpotlightCard>

          <SpotlightCard className="tile" spotlightColor="rgba(255, 122, 61, 0.16)">
            <span className="tile__icon tile__icon--warn">
              <Icon name="alert" />
            </span>
            <h3>Novedades en la vía</h3>
            <p>Derrumbes, obras y trancones que cambian tu tiempo de viaje.</p>
            <div className="alerts">
              {alertas.data?.length === 0 && <span className="alert alert--ok">Sin novedades activas</span>}
              {alertas.data?.slice(0, 2).map(a => (
                <span key={a.id} className={`alert alert--${SEVERIDAD[a.severidad] ?? 'warn'}`}>
                  {accent(a.titulo)}
                </span>
              ))}
            </div>
          </SpotlightCard>

          <SpotlightCard className="tile" spotlightColor="rgba(24, 182, 122, 0.16)">
            <span className="tile__icon tile__icon--ok">
              <Icon name="coin" />
            </span>
            <h3>Tarifa antes de salir</h3>
            <p>Sabes cuánto pagas en cada tramo, sin sorpresas.</p>
            {t && (
              <div className="fares">
                <div className="fare">
                  <span>{[...new Set(integradas.map(l => modeLabel(l.modo)))].join(' y ')}</span>
                  <b>{rango(integradas.map(l => l.tarifa))}</b>
                </div>
                <div className="fare">
                  <span>Informales</span>
                  <b>{rango(informales.map(l => l.tarifa))}</b>
                </div>
                <small className="fare__note">Integrados: el segundo abordaje en {t.ventana_integracion_min} min no se cobra.</small>
              </div>
            )}
          </SpotlightCard>
        </div>
      </div>
    </section>
  );
}
