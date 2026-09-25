import { useEffect, useRef, useState } from 'react';
import SplitText from './reactbits/SplitText';
import Icon from './Icon';
import { api } from '../lib/api';
import { routeStore } from '../lib/routeStore';
import { accent } from '../lib/text';
import { eventIconSvg } from '../data/eventIcons';
import { SYSTEMS, WALK_COLOR, eventType, inCB, systemOf, toLatLng } from '../data/mapStyle';
import { createGoogleEngine, createLeafletEngine } from '../lib/mapEngines';

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
const MAP_ID = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID';
const HUB_TYPES = new Set(['portal', 'estacion_cable']);
const LABEL_LEFT = new Set(['Mirador del Paraiso']);
const ROUTE_COLORS = { cable: SYSTEMS.cable.color, formal: SYSTEMS.formal.color, informal: SYSTEMS.informal.color, acceso: WALK_COLOR };

function normalize(capas, lugares, alertas) {
  const lines = capas.features
    .filter(f => f.properties.capa === 'linea' && f.geometry?.type === 'LineString')
    .map(f => ({ ...f.properties, system: systemOf(f.properties.tipo), path: f.geometry.coordinates.map(toLatLng) }));
  const pylons = capas.features.filter(f => f.properties.capa === 'pilona').map(f => toLatLng(f.geometry.coordinates));
  const places = lugares.lugares.map(l => ({ ...l, pos: { lat: l.lat, lng: l.lon } }));
  const events = alertas
    .filter(a => a.geometria)
    .map(a => {
      const coords = a.geometria.type === 'Point' ? [a.geometria.coordinates] : a.geometria.coordinates.flat(a.geometria.type === 'Polygon' ? 1 : 0);
      return { ...a, pos: toLatLng(coords[Math.floor(coords.length / 2)]) };
    });
  return { lines, pylons, places, events };
}

const stopHtml = p =>
  HUB_TYPES.has(p.tipo)
    ? `<div class="pin stop stop--hub ${LABEL_LEFT.has(p.nombre) ? 'stop--left' : ''}" style="--c:${SYSTEMS.cable.color}"><i></i><span>${accent(p.nombre)}</span></div>`
    : `<div class="pin place"><i></i><span>${accent(p.nombre)}</span></div>`;

const eventHtml = ev =>
  `<div class="pin ev ${ev.severidad === 'alta' ? 'ev--severe' : ''}" style="--c:${eventType(ev.tipo).color}"><b class="ev__badge">${eventIconSvg(ev.tipo)}</b><span class="ev__label">${accent(ev.titulo)}</span></div>`;

function pathSampler(path) {
  const cum = [0];
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1];
    const b = path[i];
    cum.push(cum[i - 1] + Math.hypot(b.lat - a.lat, (b.lng - a.lng) * Math.cos((a.lat * Math.PI) / 180)));
  }
  const total = cum[cum.length - 1] || 1;
  return t => {
    const d = t * total;
    let i = 1;
    while (i < cum.length - 1 && cum[i] < d) i++;
    const f = (d - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
    return { lat: path[i - 1].lat + (path[i].lat - path[i - 1].lat) * f, lng: path[i - 1].lng + (path[i].lng - path[i - 1].lng) * f };
  };
}

function overviewPoints(data) {
  return [
    ...data.lines.flatMap(l => l.path).filter(inCB),
    ...data.places.map(p => p.pos).filter(inCB),
    ...data.events.map(e => e.pos).filter(inCB)
  ];
}

function buildLayers(engine, data, onSelect) {
  const systems = Object.fromEntries(Object.keys(SYSTEMS).map(k => [k, []]));
  const events = {};
  const markers = {};
  const byId = new Map(data.lines.map(l => [l.id, l]));

  // Resalta bajo cada línea afectada el color de la novedad que la afecta.
  data.events.forEach(ev => {
    (events[ev.tipo] ??= []).push(
      ...ev.lineas_afectadas
        .map(id => byId.get(id))
        .filter(Boolean)
        .map(l => engine.polyline({ path: l.path, color: eventType(ev.tipo).color, weight: 16, opacity: 0.35, glow: true, z: 0 }))
    );
  });

  data.lines.forEach(l => {
    const s = SYSTEMS[l.system];
    const dash = s.style === 'solid' ? null : s.style;
    systems[l.system].push(engine.polyline({ path: l.path, color: s.color, weight: l.system === 'cable' ? 6 : 5, dash, flow: Boolean(dash), casing: true, z: 2 }));
  });

  data.pylons.forEach(pos => systems.cable.push(engine.marker({ pos, html: '<div class="pin pylon"></div>', title: 'Pilona del TransMiCable', z: 1 })));
  data.places.forEach(p => engine.marker({ pos: p.pos, html: stopHtml(p), title: accent(p.nombre), z: HUB_TYPES.has(p.tipo) ? 2 : 1 }));

  data.events.forEach(ev => {
    const m = engine.marker({ pos: ev.pos, html: eventHtml(ev), title: `${eventType(ev.tipo).label}: ${accent(ev.titulo)}`, onClick: () => onSelect(ev.id), z: 3 });
    events[ev.tipo].push(m);
    markers[ev.id] = m;
  });

  const vehicles = data.lines
    .filter(l => inCB(l.path[0]) && l.path.length > 1)
    .map((l, i) => {
      const v = engine.vehicle({ pos: l.path[0], color: SYSTEMS[l.system].color });
      systems[l.system].push(v);
      return { v, sample: pathSampler(l.path), speed: l.system === 'cable' ? 1 / 14000 : 1 / 26000, phase: i * 0.21 };
    });

  engine.fit(overviewPoints(data));
  return { systems, events, markers, vehicles };
}

function drawRoute(engine, route) {
  const handles = [];
  route.tramos
    .filter(t => t.geometria?.type === 'LineString' && t.modo !== 'directo')
    .forEach(t => {
      const walk = t.modo === 'acceso';
      handles.push(
        engine.polyline({
          path: t.geometria.coordinates.map(toLatLng),
          color: ROUTE_COLORS[t.modo] ?? WALK_COLOR,
          weight: walk ? 5 : 9,
          dash: walk ? 'short' : null,
          casing: true,
          z: 8
        })
      );
    });
  const ends = [
    [route.origen, 'A'],
    [route.destino, 'B']
  ].filter(([p]) => p);
  ends.forEach(([p, letter]) =>
    handles.push(engine.marker({ pos: { lat: p.lat, lng: p.lon }, html: `<div class="pin route-end">${letter}</div>`, title: accent(p.nombre), z: 5 }))
  );
  const points = [
    ...route.tramos.filter(t => t.geometria?.type === 'LineString').flatMap(t => t.geometria.coordinates.map(toLatLng)),
    ...ends.map(([p]) => ({ lat: p.lat, lng: p.lon }))
  ];
  if (points.length) engine.fit(points, 60);
  return handles;
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

function timeAgo(iso, now) {
  const min = Math.max(1, Math.round((now - Date.parse(iso)) / 60000));
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  return h < 24 ? `hace ${h} h` : `hace ${Math.round(h / 24)} d`;
}

export default function LiveMapSection() {
  const mapRef = useRef(null);
  const engineRef = useRef(null);
  const layers = useRef(null);
  const [engineName, setEngineName] = useState(null);
  const [engineVersion, setEngineVersion] = useState(0);
  const [tilesReady, setTilesReady] = useState(false);
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [hiddenSystems, setHiddenSystems] = useState(() => new Set());
  const [hiddenTypes, setHiddenTypes] = useState(() => new Set());
  const [selected, setSelected] = useState(null);
  const [route, setRoute] = useState(null);
  const [now, setNow] = useState(null);

  // Se lee en un efecto (no en el estado inicial) para que el primer render coincida con el HTML pre-renderado.
  useEffect(() => {
    setRoute(routeStore.get());
    return routeStore.subscribe(setRoute);
  }, []);

  useEffect(() => {
    setNow(Date.now());
    Promise.all([api.capas(), api.lugares(), api.alertas()])
      .then(([capas, lugares, alertas]) => setData(normalize(capas, lugares, alertas)))
      .catch(() => setLoadError(true));
  }, []);

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
    setTilesReady(false);

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
      engineRef.current = engine;
      engine.onReady(() => !cancelled && setTilesReady(true));
      setEngineVersion(v => v + 1);
    })();

    return () => {
      cancelled = true;
      engineRef.current = null;
      layers.current = null;
      engine?.destroy();
    };
  }, [engineName]);

  useEffect(() => {
    const engine = engineRef.current;
    if (!engine || !data) return;
    layers.current = buildLayers(engine, data, setSelected);
    const stop = animateVehicles(layers.current.vehicles);
    return stop;
  }, [engineVersion, data]);

  useEffect(() => {
    const l = layers.current;
    if (!l) return;
    Object.entries(l.systems).forEach(([k, list]) => list.forEach(x => x.show(!hiddenSystems.has(k))));
    Object.entries(l.events).forEach(([k, list]) => list.forEach(x => x.show(!hiddenTypes.has(k))));
    Object.entries(l.markers).forEach(([id, m]) => m.el?.firstElementChild?.classList.toggle('is-selected', id === selected));
  }, [hiddenSystems, hiddenTypes, selected, engineVersion, data]);

  useEffect(() => {
    const engine = engineRef.current;
    const ev = data?.events.find(e => e.id === selected);
    if (engine && ev) engine.flyTo(ev.pos, 15.5);
  }, [selected, engineVersion, data]);

  useEffect(() => {
    const engine = engineRef.current;
    if (!engine || !route || !data) return;
    const handles = drawRoute(engine, route);
    return () => handles.forEach(h => h.show(false));
  }, [route, engineVersion, data]);

  const selectEvent = ev => {
    setHiddenTypes(set => (set.has(ev.tipo) ? toggleIn(set, ev.tipo) : set));
    setSelected(ev.id);
  };

  const showAll = () => {
    setSelected(null);
    setHiddenSystems(new Set());
    setHiddenTypes(new Set());
    routeStore.set(null);
    if (engineRef.current && data) engineRef.current.fit(overviewPoints(data));
  };

  const lineCounts = data?.lines.reduce((acc, l) => ({ ...acc, [l.system]: (acc[l.system] ?? 0) + 1 }), {}) ?? {};
  const typeCounts = data?.events.reduce((acc, e) => ({ ...acc, [e.tipo]: (acc[e.tipo] ?? 0) + 1 }), {}) ?? {};
  const feed = data ? [...data.events].sort((a, b) => Date.parse(b.actualizado_en) - Date.parse(a.actualizado_en)) : [];

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
            {loadError ? (
              <div className="gmap-loading gmap-loading--error">No pudimos cargar las rutas en vivo. Intenta recargar la página.</div>
            ) : (
              !(tilesReady && data) && <div className="gmap-loading">Cargando mapa de Ciudad Bolívar…</div>
            )}
            <div className="livemap__status">
              <span className="live-dot" /> En vivo
            </div>
            {route && (
              <div className="livemap__route">
                <span>
                  <b>
                    {route.from} <Icon name="arrow" size={13} /> {route.to}
                  </b>
                  {route.minutes} min · {route.legs.filter(l => l.kind !== 'walk').length} tramos
                </span>
                <button type="button" onClick={() => routeStore.set(null)} aria-label="Quitar ruta del mapa">
                  <Icon name="close" size={16} />
                </button>
              </div>
            )}
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
                      <b>
                        {s.label}
                        {data && <span className="legend-row__count">{lineCounts[k] ?? 0}</span>}
                      </b>
                      <small>{s.desc}</small>
                    </span>
                    <span className="legend-row__check" aria-hidden="true" />
                  </button>
                );
              })}
            </div>

            <div className="legend__group">
              <h3>Novedades</h3>
              {!data && <p className="legend__empty">{loadError ? 'No disponibles por ahora.' : 'Cargando novedades…'}</p>}
              {data && data.events.length === 0 && <p className="legend__empty">Sin novedades reportadas. ¡Buen viaje!</p>}
              {Object.entries(typeCounts).map(([k, count]) => {
                const t = eventType(k);
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
                        <span className="legend-row__count">{count}</span>
                      </b>
                      <small>{t.desc}</small>
                    </span>
                    <span className="legend-row__check" aria-hidden="true" />
                  </button>
                );
              })}
              {data && data.events.some(e => e.lineas_afectadas.length) && (
                <p className="legend__hint">
                  <i className="mini-swatch mini-swatch--glow" style={{ '--c': '#f59e0b' }} /> El resplandor marca las líneas afectadas.
                </p>
              )}
            </div>

            {feed.length > 0 && (
              <div className="legend__group">
                <h3>Qué está pasando</h3>
                <ul className="feed">
                  {feed.map(ev => (
                    <li key={ev.id}>
                      <button type="button" className={`feed-item ${selected === ev.id ? 'is-active' : ''}`} onClick={() => selectEvent(ev)}>
                        <span className="ev-dot" style={{ '--c': eventType(ev.tipo).color }} dangerouslySetInnerHTML={{ __html: eventIconSvg(ev.tipo, 14) }} />
                        <span className="feed-item__text">
                          <b>{accent(ev.titulo)}</b>
                          <small>
                            {accent(ev.descripcion) || eventType(ev.tipo).label}
                            {ev.retraso_seg > 0 && !/\+\s?\d+\s?min/i.test(ev.descripcion) && ` · +${Math.round(ev.retraso_seg / 60)} min`}
                          </small>
                        </span>
                        {now && <time dateTime={ev.actualizado_en}>{timeAgo(ev.actualizado_en, now)}</time>}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        </div>
      </div>
    </section>
  );
}
