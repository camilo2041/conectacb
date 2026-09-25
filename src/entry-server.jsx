import { renderToString } from 'react-dom/server';
import App from './App.jsx';
import { preloadSections } from './lib/lazySection.jsx';

export async function render() {
  await preloadSections();
  return renderToString(<App />);
}
