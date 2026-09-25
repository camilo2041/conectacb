import SpotlightCard from './reactbits/SpotlightCard';
import BlurText from './reactbits/BlurText';
import Icon from './Icon';

export default function Benefits() {
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
              <span className="bubble bubble--me">¿Cómo llego a Portal Tunal?</span>
              <span className="bubble">Toma el cable en Manitas: llegas en 11 min</span>
            </div>
          </SpotlightCard>

          <SpotlightCard className="tile" spotlightColor="rgba(122, 60, 255, 0.14)">
            <span className="tile__icon">
              <Icon name="route" />
            </span>
            <h3>Una sola ruta</h3>
            <p>Formal e informal combinados en la misma recomendación.</p>
            <div className="mode-dots">
              {['#ff5a3d', '#1f63ff', '#12a150'].map(c => (
                <i key={c} style={{ background: c }} />
              ))}
            </div>
          </SpotlightCard>

          <SpotlightCard className="tile" spotlightColor="rgba(255, 122, 61, 0.16)">
            <span className="tile__icon tile__icon--warn">
              <Icon name="alert" />
            </span>
            <h3>Alertas de la comunidad</h3>
            <p>Bloqueos, derrumbes y demoras reportados en tiempo real.</p>
            <div className="alerts">
              <span className="alert alert--crit">Derrumbe · Vía a Quiba</span>
              <span className="alert alert--ok">Cable operando normal</span>
            </div>
          </SpotlightCard>

          <SpotlightCard className="tile" spotlightColor="rgba(24, 182, 122, 0.16)">
            <span className="tile__icon tile__icon--ok">
              <Icon name="coin" />
            </span>
            <h3>Tarifa antes de salir</h3>
            <p>Sabes cuánto pagas en cada tramo, sin sorpresas.</p>
            <div className="fare">
              <span>Total del viaje</span>
              <b>$7.200</b>
            </div>
          </SpotlightCard>
        </div>
      </div>
    </section>
  );
}
