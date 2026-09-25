import { Suspense } from 'react';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import ModesBand from './components/ModesBand';
import Footer from './components/Footer';
import { lazySection } from './lib/lazySection';
import './styles/sections.css';

// Cada id coincide con el <section> que renderiza el componente.
const Planner = lazySection('planear', () => import('./components/Planner'));
const Stats = lazySection('cifras', () => import('./components/Stats'));
const LiveMapSection = lazySection('mapa', () => import('./components/LiveMapSection'));
const Benefits = lazySection('beneficios', () => import('./components/Benefits'));
const HowItWorks = lazySection('como-funciona', () => import('./components/HowItWorks'));
const Statement = lazySection('por-que', () => import('./components/Statement'));
const AppSection = lazySection('app', () => import('./components/AppSection'));
const FinalCTA = lazySection('empieza', () => import('./components/FinalCTA'));

const Lazy = ({ component: Component }) => (
  <Suspense fallback={null}>
    <Component />
  </Suspense>
);

export default function App() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <ModesBand />
        <div className="sheet">
          <Lazy component={Planner} />
          <Lazy component={Stats} />
          <Lazy component={LiveMapSection} />
          <Lazy component={Benefits} />
          <Lazy component={HowItWorks} />
        </div>
        <Lazy component={Statement} />
        <Lazy component={AppSection} />
        <Lazy component={FinalCTA} />
      </main>
      <Footer />
    </>
  );
}
