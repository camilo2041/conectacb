import CardSwap, { Card } from './reactbits/CardSwap';
import SplitText from './reactbits/SplitText';
import Icon from './Icon';

const STEPS = [
  { title: 'Escribe tu destino', text: 'Por WhatsApp o en la web, con tus propias palabras.' },
  { title: 'La IA combina todo', text: 'Horarios de TransMiCable y SITP, más colectivos y rutas veredales.' },
  { title: 'Sal a la hora justa', text: 'Recibe tu ruta, tu tarifa y avisos si algo cambia.' }
];

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

export default function HowItWorks() {
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
        </div>

        <div className="swap-stage" aria-hidden="true">
          <CardSwap width={380} height={290} cardDistance={48} verticalDistance={56} delay={4200} pauseOnHover skewAmount={4}>
            <Card customClass="screen">
              <Screen icon="route" title="Ruta sugerida" tag="Más rápida">
                <div className="screen__big">
                  37 <small>min</small>
                </div>
                <div className="screen__legs">
                  <span style={{ '--c': '#12a150' }}>Veredal 24′</span>
                  <span style={{ '--c': '#ff5a3d' }}>TransMiCable 13′</span>
                </div>
              </Screen>
            </Card>
            <Card customClass="screen">
              <Screen icon="pin" title="Paradero cercano">
                <div className="screen__row">
                  <b>Estación Manitas</b>
                  <span>a 350 m · 4 min caminando</span>
                </div>
                <div className="screen__row">
                  <b>Colectivo Jerusalén</b>
                  <span>pasa en 6 min</span>
                </div>
              </Screen>
            </Card>
            <Card customClass="screen">
              <Screen icon="alert" title="Alerta en tu ruta" tag="Hace 5 min">
                <div className="screen__alert">Derrumbe parcial en la vía a Quiba</div>
                <div className="screen__row">
                  <b>Nueva ruta</b>
                  <span>Te desviamos por Sierra Morena, +6 min</span>
                </div>
              </Screen>
            </Card>
            <Card customClass="screen">
              <Screen icon="clock" title="Llegada estimada">
                <div className="screen__big">
                  7:42 <small>a. m.</small>
                </div>
                <div className="screen__progress">
                  <i />
                </div>
                <span className="screen__muted">Sal en 3 minutos para no esperar</span>
              </Screen>
            </Card>
          </CardSwap>
        </div>
      </div>
    </section>
  );
}
