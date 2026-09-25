# ConectaCB API

Backend en **FastAPI** para movilidad integrada en Ciudad Bolívar (Bogotá).
Combina la **red vial** (OSRM), **TransMiCable / TransMilenio / SITP**, **colectivos**
y **rutas veredales**, con **novedades en vivo**, **horarios**, **tarifas integradas**
y un **asistente en lenguaje natural**. Todo se expone como API REST.

## Estado

Incluye y probado (OSRM real + 19 pruebas automatizadas):

- Ruteo multimodal con costo `(tiempo, tarifa, transbordos)` o ponderado.
- Origen/destino por **coordenadas o por nombre** (gazetteer local + OpenStreetMap).
- TransMiCable con **trazado y estaciones reales** (desde `Pilona_cable.geojson`).
- Novedades/alertas en vivo (CRUD) que afectan el ruteo.
- Horarios/espera por hora y tarifas integradas.
- Salida para mapa (`/ruta/mapa`, `/capas`, `/cable/pilonas`) y asistente NL.

Pendiente para producción: auth del admin de alertas, rate-limit/caché, base de
datos (hoy alertas en JSON), OSRM propio y datos GTFS reales. El front/WhatsApp
va del lado del cliente; esta API ya expone todo lo necesario.

## Estructura

```
app/
  config.py     configuracion (rutas de datos, OSRM, velocidades, CORS)
  models.py     modelos Pydantic de request/response
  geo.py        utilidades geometricas puras (haversine, point-in-polygon)
  tiempo.py     hora/dia, horarios de servicio y espera por frecuencia
  zones.py      zonas SITP (poligonos)
  cable.py      pilonas del cable (trazado real)
  informal.py   carga de lineas (formales + informales), espera/activo/integrado
  alertas.py    novedades: modelo, almacen CRUD y afectacion a rutas
  geocoder.py   gazetteer de lugares (barrios, veredas, estaciones) + busqueda
  geocoder_externo.py  respaldo de geocoding por OpenStreetMap (Photon)
  tarifas.py    configuracion de tarifas e integracion
  osrm.py       cliente OSRM con cache y respaldo
  routing.py    grafo multimodal + Dijkstra (costo lexicografico o ponderado)
  main.py       todos los endpoints
data/
  Zonas_SITP.geojson
  rutas_informales.geojson
  rutas_informales_ciudad_bolivar.geojson
  rutas_formales.geojson        TransMiCable (TMC-01, trazado real) + Troncal TM (TMC-02)
  Pilona_cable.geojson          pilonas reales del TransMiCable (23)
  alertas.json                  novedades en vivo (CRUD)
  lugares.json                  gazetteer para geocoding/NL
  tarifas.json                  tarifas e integracion
tests/          pruebas de humo con OSRM simulado
run.py          arranque con uvicorn
```

## Instalación y ejecución

```powershell
python -m pip install -r requirements.txt
python run.py
```

Docs interactivas (Swagger): http://localhost:8000/docs

Guía para integrar la planeación de viajes de A a B (web, WhatsApp, apps):
[docs/planear-viajes.md](docs/planear-viajes.md).

## Endpoints

### Sistema
| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/health` | Estado, conteos y hora/día del servidor. |

### Zonas SITP
| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/zonas` | GeoJSON crudo de las zonas SITP. |
| GET | `/zonas/ubicacion?lat=&lon=&radio_m=` | Zona del punto y zonas cercanas. |

### Líneas (formales + informales)
| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/lineas` | Todas las líneas. |
| GET | `/lineas/{id}` | Detalle de una línea. |
| GET | `/lineas/{id}/horario?hora=&dia=` | Horario, activo y espera. |
| GET | `/horarios?hora=&dia=` | Horario/activo/espera de todas las líneas. |
| GET | `/rutas-informales` | Catálogo de líneas informales. |
| GET | `/rutas-formales` | Catálogo de líneas formales. |

### Tarifas
| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/tarifas` | Reglas de integración + tarifa por línea. |

### Geocoding / lugares
| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/lugares` | Lista de lugares conocidos (gazetteer local). |
| GET | `/geocodificar?q=&limite=&externo=` | Busca por texto: gazetteer local y, si no hay, OSM (Photon). |

El gazetteer local (`data/lugares.json`) es rápido y sin red; si no encuentra,
se usa **OpenStreetMap vía Photon** (sin API key) para barrios, direcciones o
lugares. `/ruta`, `/ruta/mapa` y `/asistente` aceptan nombres directamente.

### Alertas / novedades
| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/alertas?activas=&tipo=&solo_vigentes=` | Lista novedades. |
| GET | `/alertas/cerca?lat=&lon=&radio_m=` | Novedades cerca de un punto. |
| GET | `/alertas/{id}` | Detalle. |
| POST | `/alertas` | Crear novedad. |
| PUT | `/alertas/{id}` | Actualizar novedad. |
| DELETE | `/alertas/{id}` | Eliminar novedad. |

### Ruteo
| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | `/ruta` | Mejor ruta + alternativas. |
| POST | `/ruta/mapa` | Ruta como `FeatureCollection` por tramos (colores por modo) + novedades. |
| GET | `/capas` | Capas base del mapa: zonas + líneas + alertas + pilonas del cable. |
| GET | `/cable/pilonas` | Pilonas del TransMiCable (trazado real) como `FeatureCollection`. |

### Asistente
| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | `/asistente` | Pregunta en lenguaje natural → ruta + respuesta textual. |

## Ejemplos

### Ruta
```bash
curl -X POST http://localhost:8000/ruta -H "Content-Type: application/json" -d '{
  "origen":  {"lat": 4.575, "lon": -74.180},
  "destino": {"lat": 4.555691, "lon": -74.147484},
  "usar_directo": false,
  "hora": "12:00"
}'
```

Campos de `/ruta`:

| Campo | Default | Descripción |
| --- | --- | --- |
| `origen` / `destino` | — | Coordenadas `{lat, lon}`. **O** usa `origen_texto`/`destino_texto`. |
| `origen_texto` / `destino_texto` | — | Nombre, barrio, vereda, estación o dirección. Se geocodifica (gazetteer local + OSM). |
| `perfil` | `driving` | Perfil OSRM de la ruta directa. |
| `usar_directo` | `true` | Incluir la ruta directa en auto. `false` = mejor combinación de transporte. |
| `usar_informales` | `true` | Permitir colectivos/veredales/mototaxis. |
| `usar_formales` | `true` | Permitir TransMiCable/TransMilenio/SITP. |
| `hora` / `dia` | ahora | `"HH:MM"` y `L,M,X,J,V,S,D`. Afectan esperas y servicio activo. |
| `pesos` | `null` | Costo ponderado; `null` = orden `(tiempo, tarifa, transbordos)`. |
| `opciones.max_transbordos` | `2` | Máximo de transbordos. |
| `opciones.radio_acceso_m` | `1500` | Radio de acceso a pie. |

### Ruta por nombres (sin coordenadas)
```bash
curl -X POST http://localhost:8000/ruta -H "Content-Type: application/json" -d '{
  "origen_texto": "Quiba",
  "destino_texto": "Portal Tunal",
  "usar_directo": false,
  "hora": "12:00"
}'
```
También funciona con direcciones o lugares que **no** están en el gazetteer local,
porque cae a OpenStreetMap (Photon), p. ej. `"origen_texto": "Estadio El Campin"`.

Respuesta (resumen):
```json
{
  "distancia_m": 6211.5,
  "duracion_seg": 1275.6,
  "tarifa_total_cop": 7700.0,
  "transbordos": 1,
  "geometria": {"type": "LineString", "coordinates": [[-74.18, 4.575], "..."]},
  "tramos": [
    {"modo": "informal", "linea": "CB-07", "distancia_m": 4609.4, "duracion_seg": 638.2, "tarifa_cop": 4500.0},
    {"modo": "cable",    "linea": "TMC-01", "distancia_m": 1602.1, "duracion_seg": 367.4, "tarifa_cop": 3200.0}
  ],
  "zonas": [{"nombre": "Usme/Ciudad Bolivar", "letra": "H"}],
  "informales_usadas": ["CB-07"],
  "formales_usadas": ["TMC-01"],
  "novedades": [],
  "alternativas": []
}
```

### Alertas (crear/actualizar/eliminar)
```bash
curl -X POST http://localhost:8000/alertas -H "Content-Type: application/json" -d '{
  "tipo": "bloqueo",
  "titulo": "Bloqueo en la via a Mochuelo",
  "severidad": "alta",
  "retraso_seg": 900,
  "lineas_afectadas": ["CB-04", "CB-09"],
  "geometria": {"type": "Point", "coordinates": [-74.148186, 4.508277]},
  "vigencia": {"desde": "2026-09-24T06:00:00", "hasta": null}
}'
```

### Asistente
```bash
curl -X POST http://localhost:8000/asistente -H "Content-Type: application/json" -d '{
  "texto": "como llego de Cazuca a Juan Pablo II",
  "usar_directo": false,
  "hora": "12:00"
}'
```
Respuesta: `{ "respuesta": "Ruta de 21 min, tarifa $7,700. Camina, luego Mototaxi Cazuca - Mirador del Paraiso, luego camina, luego TransMiCable Tunal (Portal Tunal - Mirador del Paraiso), luego camina. 1 transbordo(s).", "origen": {...}, "destino": {...}, "ruta": {...} }`

### Mapa
```bash
curl -X POST http://localhost:8000/ruta/mapa -H "Content-Type: application/json" -d '{
  "origen_texto": "Cazuca",
  "destino_texto": "Juan Pablo II",
  "usar_directo": false
}'
```
Devuelve un `FeatureCollection` con un Feature por tramo (propiedad `color` según
`modo`) y Features de las novedades. Colores: `cable` `#8B5CF6`, `formal` `#10B981`,
`informal` `#F59E0B`, `acceso` `#9CA3AF`, `directo` `#2563EB`.

## Cómo funciona el ruteo

1. Ruta **directa** O→D con OSRM (si `usar_directo`).
2. Se toman las **líneas candidatas** (formales e informales) con parada a menos de
   `radio_acceso_m` del origen/destino y se **expanden** con líneas "puente" por
   transbordo.
3. **Grafo** con nodos = origen, destino y paradas. Aristas: acceso a pie, abordar
   (espera + tarifa), recorrer y bajar.
4. **Dijkstra** con costo:
   - por defecto **lexicográfico** `(tiempo, tarifa, transbordos)`;
   - o ponderado si envías `pesos`.
5. Ajustes de realidad:
   - **Horarios**: una línea fuera de horario no se puede abordar; la espera se
     calcula como media cabeza de frecuencia (`frecuencia_min/2`) si existe.
    - **Tarifas integradas**: TransMiCable/TransMilenio/SITP comparten sistema; el
      segundo abordaje integrado seguido **no cobra** (ver `tarifas.json`).
   - **Novedades**: una alerta que afecta una línea (por `lineas_afectadas` o por
     cercanía a su geometría) suma su `retraso_seg` y aparece en `novedades`.

## Datos reales del TransMiCable

`data/Pilona_cable.geojson` son las **23 pilonas reales** del TransMiCable
(Ciudad Bolívar) en 3 subtramos:

| subtramo | nombre | pilonas |
| --- | --- | --- |
| 101 | Tunal - Juan Pablo II | 1-11 |
| 102 | Juan Pablo II - Manitas | 12-16 |
| 103 | Manitas - Mirador del Paraíso | 17-23 |

Con ellas se reconstruyó el trazado real de `TMC-01` en `rutas_formales.geojson`:
**27 vértices** (23 pilonas + 4 estaciones), **3.398 m** y ~**13 min** de recorrido.
Las estaciones (coordenadas reales de OSM) son:

| estación | lat | lon |
| --- | --- | --- |
| Portal Tunal | 4.569675 | -74.139249 |
| Juan Pablo II | 4.555691 | -74.147484 |
| Manitas | 4.550440 | -74.150580 |
| Mirador del Paraíso | 4.550082 | -74.158767 |

Las pilonas se exponen en `GET /cable/pilonas` y en la capa `pilona` de `GET /capas`.
Las rutas informales de Ciudad Bolívar usan **anclas reales** (OSM/Photon) y conectan
con las estaciones reales del cable (p. ej. `CB-02` y `CB-07` terminan en Mirador del
Paraíso; `CB-03` arranca en Juan Pablo II; `CB-01` termina en Portal Tunal).

## Formatos de datos (pluggable)

### Líneas (informales y formales)
`FeatureCollection` de `LineString`; las paradas son los vértices, o se declaran en
`properties.paradas` (lista de `[lon, lat]`, útil para el cable: 4 estaciones sobre
27 vértices). El campo `tipo` decide el modo del tramo: `informal`, `cable`, `formal`,
`troncal`, `sitp`…
```json
{"type": "Feature", "properties": {
  "id": "CB-01", "nombre": "Colectivo Arborizadora Alta - Portal Tunal", "modo": "colectivo",
  "tipo": "informal", "tarifa": 3000, "tiempo_espera_seg": 240, "frecuencia_min": 6,
  "horario": {"ini": "04:30", "fin": "23:00", "dias": ["L","M","X","J","V","S","D"]},
  "velocidad_kmh": 20
}, "geometry": {"type": "LineString", "coordinates": [[-74.162493, 4.567694], "..."]}}
```
Se cargan todos los `rutas_informales*.geojson` y `rutas_formales*.geojson`.

### Alertas (`data/alertas.json`)
Campos: `id, tipo, titulo, descripcion, severidad, retraso_seg, lineas_afectadas,
geometria (Point/LineString/Polygon), vigencia {desde, hasta}, fuente, activo`.

### Lugares (`data/lugares.json`)
`{ "nombre", "tipo", "lat", "lon", "alias": [...] }` para geocoding/NL.

### Tarifas (`data/tarifas.json`)
`moneda, sistema_integrado, ventana_integracion_min, tipos_integrados, tarifa_base_troncal`.

## Configuración (variables de entorno, prefijo `RUTAS_`)

| Variable | Default | Descripción |
| --- | --- | --- |
| `RUTAS_OSRM_BASE_URL` | `https://router.project-osrm.org` | Servidor OSRM. |
| `RUTAS_RADIO_ACCESO_M` | `1500` | Radio de acceso a paradas. |
| `RUTAS_RADIO_TRANSBORDO_M` | `400` | Radio para transbordo a pie. |
| `RUTAS_VELOCIDAD_CAMINATA_KMH` | `4.8` | Velocidad de caminata. |
| `RUTAS_INFORMALES_GLOB` / `RUTAS_FORMALES_GLOB` | `data/rutas_*.geojson` | Patrones de carga. |
| `RUTAS_ALERTAS_PATH` / `RUTAS_LUGARES_PATH` / `RUTAS_TARIFAS_PATH` | `data/*.json` | Datos. |
| `RUTAS_PILONAS_PATH` | `data/Pilona_cable.geojson` | Pilonas del cable. |
| `RUTAS_GEOCODER_EXTERNO` | `true` | Respaldo de geocoding por OpenStreetMap (Photon). |
| `RUTAS_PHOTON_URL` | `https://photon.komoot.io` | Servicio de geocoding OSM. |
| `RUTAS_CORS_ORIGINS` | `*` | Orígenes CORS (coma). |

## Pruebas

```powershell
python -m pytest -q
```

## Limitaciones

- El **OSRM público** solo trae perfil `driving`; `walking`/`cycling` se comportan
  como auto. Para perfiles reales, auto-hospedar OSRM.
- El **trazado del cable** (TMC-01) y las **estaciones** son reales; las **pilonas**
  son reales (`Pilona_cable.geojson`). La troncal `TMC-02` y las rutas urbanas de
  `rutas_informales.geojson` siguen siendo **mock**. Las rutas de Ciudad Bolívar usan
  anclas reales (OSM) pero con trazados aproximados.
- Los datos de alertas, lugares y tarifas son de ejemplo, listos para reemplazar por
  fuentes reales (GTFS, operadores, etc.).
- La ruta directa en auto no incluye combustible/parqueo; usa `usar_directo:false`
  para comparar transporte público/informal.
- `max_transbordos` acota la expansión de líneas candidatas, no es corte duro en Dijkstra.
- Accesos y transbordos a pie se miden en línea recta (haversine).
- Las alertas se guardan en un JSON (no hay base de datos); el `POST/PUT/DELETE`
  requiere que el proceso tenga permiso de escritura.
