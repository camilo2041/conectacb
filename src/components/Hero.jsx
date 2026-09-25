import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'motion/react';
import Magnet from './reactbits/Magnet';
import Icon from './Icon';
import banner from '../assets/banner.jpg';
import bannerMobile from '../assets/banner-mobile.jpg';
import { WHATSAPP_URL } from '../config';

export default function Hero() {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] });
  const y = useTransform(scrollYProgress, [0, 1], ['0%', '18%']);
  const fade = useTransform(scrollYProgress, [0, 0.8], [1, 0.35]);

  return (
    <section className="hero" id="top" ref={ref}>
      <motion.div className="hero__media" style={{ y, opacity: fade }}>
        <img
          src={banner}
          srcSet={`${bannerMobile} 960w, ${banner} 1920w`}
          sizes="100vw"
          alt="ConectaCB: movilidad integrada con inteligencia artificial. TransMiCable al atardecer sobre las laderas de Ciudad Bolívar."
          width="1920"
          height="1082"
          fetchPriority="high"
        />
      </motion.div>

      <div className="hero__actions">
        <Magnet padding={50} magnetStrength={5}>
          <a href="#planear" className="btn btn-brand">
            Planear mi ruta <Icon name="arrow" size={18} />
          </a>
        </Magnet>
        <a href={WHATSAPP_URL} target="_blank" rel="noreferrer" className="btn btn-light">
          <Icon name="chat" size={18} /> Usar en WhatsApp
        </a>
      </div>

      <a href="#planear" className="hero__scroll" aria-label="Bajar a planear ruta">
        <span />
      </a>
    </section>
  );
}
