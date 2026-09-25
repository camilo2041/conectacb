import { useEffect, useRef, useState } from 'react';
import SplitText from './reactbits/SplitText';
import { EVENTS, EVENT_TYPES, LINES, STOPS, SYSTEMS, segment, servicePath } from '../data/network';
import { eventIconSvg } from '../data/eventIcons';
import { createGoogleEngine, createLeafletEngine } from '../lib/mapEngines';

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
const MAP_ID = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID';
const CLOSED_COLOR = '#475569';

const stopHtml = s =>
  `<div class="pin stop ${s.hub ? 'stop--hub' : ''} ${s.labelLeft ? 'stop--left' : ''}" style="--c:${SYSTEMS[s.system].color}"><i></i>${
    s.hub ? `<span>${s.name}</span>` : ''
  }</div>`;

const eventHtml = ev => {
  const t = EVENT_TYPES[ev.type];
  return `<div class="pin ev ${t.severe ? 'ev--severe' : ''}" style="--c:${t.color}"><b class="ev__badge">${eventIconSvg(ev.type)}</b><span class="ev__label">${ev.title}</span></div>`;
};

function pathSampler(path) {
  const cum = [0];
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1];
    const b = path[i];
    cum.push(cum[i - 1] + Math.hypot(b.lat - a.lat, (b.lng - a.lng) * Math.cos((a.lat * Math.PI) / 180)));
  }
  const total = cum[cum.length - 1];
  return t => {
    const d = t * total;
    let i = 1;
    while (i < cum.length - 1 && cum[i] < d) i++;
    const f = (d - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
    return { lat: path[i - 1].lat + (path[i].lat - path[i - 1].lat) * f, lng: path[i - 1].lng + (path[i].lng - path[i - 1].lng) * f };
  };
}

function buildLayers(engine, onSelect) {
  const systems = Object.fromEntries(Object.keys(SYSTEMS).map(k => [k, []]));
  const events = Object.fromEntries(Object.keys(EVENT_TYPES).map(k => [k, []]));
  const markers = {};

  EVENTS.filter(ev => ev.slow).forEach(ev =>
    events[ev.type].push(engine.polyline({ path: segment(ev.slow), color: EVENT_TYPES[ev.type].color, weight: 16, opacity: 0.5, glow: true, z: 0 }))
  );

  LINES.forEach(l => {
    const s = SYSTEMS[l.system];
    const dash = s.style === 'solid' ? null : s.style;
    systems[l.system].push(engine.polyline({ path: l.path, color: s.color, weight: l.system === 'cable' ? 6 : 5, dash, flow: Boolean(dash), casing: true, z: 2 }));
  });

  EVENTS.forEach(ev => {
    if (ev.closed) events[ev.type].push(engine.polyline({ path: segment(ev.closed), color: CLOSED_COLOR, weight: 5, dash: 'short', casing: true, z: 4 }));
    if (ev.detour)
      events[ev.type].push(engine.polyline({ path: ev.detour, color: EVENT_TYPES.desvio.color, weight: 5, dash: 'dash', flow: true, casing: true, z: 6 }));
  });

  STOPS.forEach(s => systems[s.system].push(engine.marker({ pos: s.pos, html: stopHtml(s), title: s.name, z: 1 })));

  EVENTS.forEach(ev => {
    const m = engine.marker({ pos: ev.pos, html: eventHtml(ev), title: `${EVENT_TYPES[ev.type].label}: ${ev.title}`, onClick: () => onSelect(ev.id), z: 3 });
    events[ev.type].push(m);
    markers[ev.id] = m;
  });

  const vehicles = LINES.map((l, i) => {
    const sample = pathSampler(servicePath(l.id));
    const v = engine.vehicle({ pos: l.path[0], color: SYSTEMS[l.system].color });
    systems[l.system].push(v);
    return { v, sample, speed: l.system === 'cable' ? 1 / 14000 : 1 / 24000, phase: i * 0.27 };
  });

  engine.fit([...STOPS.map(s => s.pos), ...EVENTS.map(e => e.pos)]);
  return { engine, systems, events, markers, vehicles };
}

function animateVehicles(vehicles) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return () => {};
  let raf;
  const tick = now => {
    vehicles.forEach(({ v, sample, speed, phase }) => {
      const p = (now * speed + phase) % 2;
      v.setPos(sample(p <= 1 ? p : 2 - p));
    });
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}

function toggleIn(set, key) {
  const next = new Set(set);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}

export default function LiveMapSection() {
  const mapRef = useRef(null);
  const layers = useRef(null);
  const [engineName, setEngineName] = useState(null);
  const [version, setVersion] = useState(0);
  const [ready, setReady] = useState(false);
  const [hiddenSystems, setHiddenSystems] = useState(() => new Set());
  const [hiddenTypes, setHiddenTypes] = useState(() => new Set());
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          io.disconnect();
          setEngineName(API_KEY ? 'google' : 'leaflet');
        }
      },
      { rootMargin: '400px' }
    );
    io.observe(mapRef.current);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!engineName) return;
    let cancelled = false;
    let engine;
    let stopAnimation = () => {};
    setReady(false);

    (async () => {
      const isCancelled = () => cancelled;
      try {
        engine =
          engineName === 'google'
            ? await createGoogleEngine(mapRef.current, {
                apiKey: API_KEY,
                mapId: MAP_ID,
                isCancelled,
                onAuthFailure: () => !cancelled && setEngineName('leaflet')
              })
            : await createLeafletEngine(mapRef.current, { isCancelled });
      } catch {
        if (!cancelled) setEngineName('leaflet');
        return;
      }
      if (!engine) return;
      if (cancelled) {
        engine.destroy();
        return;
      }
      layers.current = buildLayers(engine, setSelected);
      engine.onReady(() => !cancelled && setReady(true));
      stopAnimation = animateVehicles(layers.current.vehicles);
      setVersion(v => v + 1);
    })();

    return () => {
      cancelled = true;
      stopAnimation();
      layers.current = null;
      engine?.destroy();
    };
  }, [engineName]);

  useEffect(() => {
    const l = layers.current;
    if (!l) return;
    Object.entries(l.systems).forEach(([k, list]) => list.forEach(x => x.show(!hiddenSystems.has(k))));
    Object.entries(l.events).forEach(([k, list]) => list.forEach(x => x.show(!hiddenTypes.has(k))));
    Object.entries(l.markers).forEach(([id, m]) => m.el?.firstElementChild?.classList.toggle('is-selected', id === selected));
  }, [hiddenSystems, hiddenTypes, selected, version]);

  useEffect(() => {
    const l = layers.current;
    const ev = EVENTS.find(e => e.id === selected);
    if (l && ev) l.engine.flyTo(ev.pos, 15.5);
  }, [selected, version]);

  const selectEvent = ev => {
    setHiddenTypes(set => (set.has(ev.type) ? toggleIn(set, ev.type) : set));
    setSelected(ev.id);
  };

  const showAll = () => {
    setSelected(null);
    setHiddenSystems(new Set());
    setHiddenTypes(new Set());
    layers.current?.engine.fit([...STOPS.map(s => s.pos), ...EVENTS.map(e => e.pos)]);
  };

  const counts = EVENTS.reduce((acc, e) => ({ ...acc, [e.type]: (acc[e.type] ?? 0) + 1 }), {});

  return (
    <section className="section livemap" id="mapa">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">
            <span className="live-dot" /> Mapa en vivo
          </span>
          <SplitText
            text="Lo que pasa ahora en la ladera."
            tag="h2"
            className="display h2"
            textAlign="left"
            splitType="words"
            delay={80}
            duration={0.9}
            from={{ opacity: 0, y: 40 }}
            to={{ opacity: 1, y: 0 }}
          />
          <p className="lead">Cada sistema con su color y cada novedad marcada donde ocurre, reportada por la comunidad.</p>
        </div>

        <div className="livemap__panel">
          <div className="livemap__map">
            <div key={engineName ?? 'idle'} ref={mapRef} className="gmap" role="region" aria-label="Mapa de rutas y novedades de Ciudad Bolívar" />
            {!ready && <div className="gmap-loading">Cargando mapa de Ciudad Bolívar…</div>}
            <div className="livemap__status">
              <span className="live-dot" /> En vivo · hace 1 min
            </div>
            <button type="button" className="livemap__reset" onClick={showAll}>
              Ver todo
            </button>
          </div>

          <aside className="legend" aria-label="Convenciones del mapa">
            <div className="legend__group">
              <h3>Sistemas</h3>
              {Object.entries(SYSTEMS).map(([k, s]) => {
                const on = !hiddenSystems.has(k);
                return (
                  <button
                    key={k}
                    type="button"
                    className={`legend-row ${on ? '' : 'is-off'}`}
                    aria-pressed={on}
                    onClick={() => setHiddenSystems(set => toggleIn(set, k))}
                  >
                    <span className={`swatch swatch--${s.style}`} style={{ '--c': s.color }} />
                    <span className="legend-row__text">
                      <b>{s.label}</b>
                      <small>{s.desc}</small>
                    </span>
                    <span className="legend-row__check" aria-hidden="true" />
                  </button>
                );
              })}
            </div>

            <div className="legend__group">
              <h3>Novedades</h3>
              {Object.entries(EVENT_TYPES).map(([k, t]) => {
                const on = !hiddenTypes.has(k);
                return (
                  <button
                    key={k}
                    type="button"
                    className={`legend-row ${on ? '' : 'is-off'}`}
                    aria-pressed={on}
                    onClick={() => setHiddenTypes(set => toggleIn(set, k))}
                  >
                    <span className="ev-dot" style={{ '--c': t.color }} dangerouslySetInnerHTML={{ __html: eventIconSvg(k, 15) }} />
                    <span className="legend-row__text">
                      <b>
                        {t.label}
                        {k === 'trancon' && <i className="mini-swatch mini-swatch--glow" style={{ '--c': t.color }} />}
                        {k === 'desvio' && (
                          <>
                            <i className="mini-swatch mini-swatch--dash" style={{ '--c': t.color }} />
                            <i className="mini-swatch mini-swatch--short" style={{ '--c': CLOSED_COLOR }} />
                          </>
                        )}
                        {k === 'cierre' && <i className="mini-swatch mini-swatch--short" style={{ '--c': CLOSED_COLOR }} />}
                        <span className="legend-row__count">{counts[k] ?? 0}</span>
                      </b>
                      <small>{t.desc}</small>
                    </span>
                    <span className="legend-row__check" aria-hidden="true" />
                  </button>
                );
              })}
            </div>

            <div className="legend__group">
              <h3>Qué está pasando</h3>
              <ul className="feed">
                {[...EVENTS]
                  .sort((a, b) => a.ago - b.ago)
                  .map(ev => (
                    <li key={ev.id}>
                      <button
                        type="button"
                        className={`feed-item ${selected === ev.id ? 'is-active' : ''}`}
                        onClick={() => selectEvent(ev)}
                      >
                        <span
                          className="ev-dot"
                          style={{ '--c': EVENT_TYPES[ev.type].color }}
                          dangerouslySetInnerHTML={{ __html: eventIconSvg(ev.type, 14) }}
                        />
                        <span className="feed-item__text">
                          <b>{ev.title}</b>
                          <small>
                            {ev.place} · {ev.impact}
                          </small>
                        </span>
                        <time>hace {ev.ago} min</time>
                      </button>
                    </li>
                  ))}
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
