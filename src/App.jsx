import Navbar from './components/Navbar';
import Hero from './components/Hero';
import ModesBand from './components/ModesBand';
import Planner from './components/Planner';
import Stats from './components/Stats';
import LiveMapSection from './components/LiveMapSection';
import Benefits from './components/Benefits';
import HowItWorks from './components/HowItWorks';
import Statement from './components/Statement';
import AppSection from './components/AppSection';
import FinalCTA from './components/FinalCTA';
import Footer from './components/Footer';
import './styles/sections.css';

export default function App() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <ModesBand />
        <div className="sheet">
          <Planner />
          <Stats />
          <LiveMapSection />
          <Benefits />
          <HowItWorks />
        </div>
        <Statement />
        <AppSection />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
