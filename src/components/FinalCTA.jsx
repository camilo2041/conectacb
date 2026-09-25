import Aurora from './reactbits/Aurora';
import BlurText from './reactbits/BlurText';
import Magnet from './reactbits/Magnet';
import Icon from './Icon';
import { WHATSAPP_URL } from '../config';

export default function FinalCTA() {
  return (
    <section className="final" id="empieza" aria-label="Empieza ahora">
      <div className="container">
        <div className="final__panel">
          <div className="final__aurora" aria-hidden="true">
            <Aurora colorStops={['#14c3f2', '#7a3cff', '#ff7a3d']} amplitude={1.1} blend={0.55} speed={0.8} />
          </div>
          <div className="final__content">
            <BlurText as="h2" text="Tu próxima ruta empieza aquí." className="display final__title" delay={110} direction="bottom" />
            <p>Gratis para la comunidad. Sin registro, sin descargas.</p>
            <div className="final__actions">
              <Magnet padding={50} magnetStrength={4}>
                <a href={WHATSAPP_URL} target="_blank" rel="noreferrer" className="btn btn-brand">
                  <Icon name="chat" size={18} /> Empezar en WhatsApp
                </a>
              </Magnet>
              <a href="#planear" className="btn btn-light">
                Planear en la web <Icon name="arrow" size={18} />
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
