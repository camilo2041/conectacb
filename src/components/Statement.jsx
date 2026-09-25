import ScrollReveal from './reactbits/ScrollReveal';
import ScrollVelocity from './reactbits/ScrollVelocity';

export default function Statement() {
  return (
    <section className="statement" id="por-que" aria-label="Por qué ConectaCB">
      <div className="container">
        <ScrollReveal
          baseOpacity={0.12}
          enableBlur
          baseRotation={2}
          blurStrength={6}
          containerClassName="statement__reveal"
          textClassName="statement__text"
        >
          Deja de adivinar cuándo pasa tu ruta. TransMiCable, SITP, colectivos y rutas veredales, por fin en una sola respuesta.
        </ScrollReveal>
      </div>

      <div className="statement__velocity">
        <ScrollVelocity
          texts={['TransMiCable · SITP · TransMilenio ·', 'Colectivos · Rutas veredales · Jeeps ·']}
          velocity={45}
          className="velocity-text"
          numCopies={4}
        />
      </div>
    </section>
  );
}
