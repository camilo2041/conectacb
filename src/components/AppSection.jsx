import TiltedCard from './reactbits/TiltedCard';
import GradientText from './reactbits/GradientText';
import SplitText from './reactbits/SplitText';
import Magnet from './reactbits/Magnet';
import Icon from './Icon';
import badge from '../assets/badge.png';
import { WHATSAPP_URL } from '../config';

const CHANNELS = [
  { icon: 'chat', title: 'WhatsApp', text: 'El canal que ya usas' },
  { icon: 'globe', title: 'App web', text: 'Liviana, funciona con poca señal' },
  { icon: 'pin', title: 'Mapa', text: 'Paraderos y alertas cerca de ti' }
];

export default function AppSection() {
  return (
    <section className="section app" id="app">
      <div className="container app__grid">
        <div className="app__badge">
          <div className="app__halo" aria-hidden="true" />
          <TiltedCard
            imageSrc={badge}
            altText="Insignia de ConectaCB"
            captionText="ConectaCB"
            containerHeight="min(440px, 92vw)"
            containerWidth="100%"
            imageHeight="min(380px, 78vw)"
            imageWidth="min(380px, 78vw)"
            rotateAmplitude={12}
            scaleOnHover={1.06}
            showMobileWarning={false}
            showTooltip
          />
        </div>

        <div className="app__copy">
          <GradientText colors={['#14c3f2', '#1f63ff', '#7a3cff', '#ea3f9a', '#14c3f2']} animationSpeed={6} showBorder className="app__pill">
            Movilidad integrada con IA
          </GradientText>
          <SplitText
            text="Tu ciudad, conectada."
            tag="h2"
            className="display h2"
            textAlign="left"
            splitType="chars"
            delay={30}
            duration={0.8}
            from={{ opacity: 0, y: 40, rotateX: -60 }}
            to={{ opacity: 1, y: 0, rotateX: 0 }}
          />
          <p className="lead">Llévalo en el bolsillo. Pregunta, recibe tu ruta y reporta novedades desde donde estés.</p>

          <ul className="channels">
            {CHANNELS.map(c => (
              <li key={c.title}>
                <span className="channels__icon">
                  <Icon name={c.icon} />
                </span>
                <b>{c.title}</b>
                <span>{c.text}</span>
              </li>
            ))}
          </ul>

          <div className="app__actions">
            <Magnet padding={40} magnetStrength={5}>
              <a href={WHATSAPP_URL} target="_blank" rel="noreferrer" className="btn btn-brand">
                <Icon name="chat" size={18} /> Escribir por WhatsApp
              </a>
            </Magnet>
            <a href="#planear" className="btn btn-outline">
              Abrir app web
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
