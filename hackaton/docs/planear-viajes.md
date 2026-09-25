# Planear viajes de A a B con la API de ConectaCB

Guía para integrar la planeación de viajes (web, WhatsApp, apps) con la API de rutas.
Cubre qué endpoint usar, cómo pedir una ruta, cómo leer la respuesta y qué hacer cuando no hay ruta.

## URL base

| Entorno | URL base | Documentación interactiva (Swagger) |
| --- | --- | --- |
| Producción | `https://conectacb.autonomiaydesarrollo.com/api` | `https://conectacb.autonomiaydesarrollo.com/api/docs` |
| Local | `http://localhost:8000` | `http://localhost:8000/docs` |

En producción la API solo acepta `GET` y `POST`, y las alertas son de solo lectura (ver [Restricciones](#restricciones-en-producción)).
No requiere API key.

## Qué endpoint usar

| Necesitas | Endpoint | Entrada |
| --- | --- | --- |
| La mejor ruta con todo el detalle | `POST /ruta` | Coordenadas o nombres de A y B |
| Responder una pregunta en texto libre (chatbot) | `POST /asistente` | `"como llego de Quiba a Portal Tunal"` |
| Dibujar la ruta en un mapa | `POST /ruta/mapa` | Igual que `/ruta` |
| Convertir un nombre en coordenadas (autocompletar) | `GET /geocodificar?q=` | Texto |
| Lista de lugares conocidos | `GET /lugares` | — |
| Nombre y datos de una línea (`CB-07`, `TMC-01`…) | `GET /lineas/{id}` | Id de la línea |

## Flujo recomendado

1. **Ubica A y B.** Envía coordenadas si las tienes (GPS del usuario, pin en el mapa). Si solo tienes texto, puedes mandarlo directo en `origen_texto`/`destino_texto`, o resolverlo antes con `GET /geocodificar` para mostrar sugerencias.
2. **Pide la ruta** con `POST /ruta`, `"usar_directo": false` y la `hora` del viaje.
3. **Revisa que haya ruta:** si `tramos` viene vacío, no hay servicio que conecte A y B a esa hora.
4. **Muestra los tramos** en orden, con el nombre de cada línea (`GET /lineas/{id}`), la duración y la tarifa.
5. **Opcional:** dibuja la ruta con `POST /ruta/mapa` o con la `geometria` de cada tramo.

## `POST /ruta`

### Petición

| Campo | Tipo | Por defecto | Descripción |
| --- | --- | --- | --- |
| `origen` | `{lat, lon}` | — | Coordenadas de A. O usa `origen_texto`. |
| `destino` | `{lat, lon}` | — | Coordenadas de B. O usa `destino_texto`. |
| `origen_texto` | string | — | Barrio, vereda, estación o dirección de A. Se busca en los lugares conocidos y, si no está, en OpenStreetMap. |
| `destino_texto` | string | — | Igual, para B. |
| `usar_directo` | bool | **`true`** | Incluye la ruta en carro por la vía. **Envía `false` para planear en transporte público e informal**; con `true` la mejor opción puede ser el carro. |
| `usar_formales` | bool | `true` | Permite TransMiCable, TransMilenio y SITP. |
| `usar_informales` | bool | `true` | Permite colectivos, busetas, camperos y mototaxis. |
| `hora` | `"HH:MM"` | hora del servidor | Hora de salida (hora de Bogotá). Define qué líneas están en servicio y cuánto se espera. |
| `dia` | `L M X J V S D` | día del servidor | Día de la semana del viaje. |
| `pesos` | objeto | `null` | Cómo elegir la mejor ruta. `null` = primero la más rápida, luego la más barata, luego la de menos transbordos. Ver [Priorizar precio o transbordos](#priorizar-precio-o-transbordos). |
| `opciones.max_transbordos` | int 0–5 | `2` | Transbordos máximos. |
| `opciones.radio_acceso_m` | número 100–10000 | `1500` | Distancia máxima a pie hasta una parada. |
| `opciones.max_paradas_por_extremo` | int 1–30 | `6` | Paradas candidatas cerca de A y de B. |
| `perfil` | `driving` | `driving` | Solo afecta la ruta en carro (`usar_directo`). |

Envía siempre `hora` y `dia` cuando el viaje no es "ahora": las líneas tienen horario y fuera de él no se pueden abordar.

### Ejemplo: por coordenadas

```bash
curl -X POST https://conectacb.autonomiaydesarrollo.com/api/ruta \
  -H "Content-Type: application/json" \
  -d '{
    "origen":  {"lat": 4.5794, "lon": -74.1812},
    "destino": {"lat": 4.555691, "lon": -74.147484},
    "usar_directo": false,
    "hora": "07:30",
    "dia": "L"
  }'
```

### Ejemplo: por nombres

```bash
curl -X POST https://conectacb.autonomiaydesarrollo.com/api/ruta \
  -H "Content-Type: application/json" \
  -d '{"origen_texto": "Cazuca", "destino_texto": "Juan Pablo II", "usar_directo": false, "hora": "07:30"}'
```

### Ejemplo: JavaScript

```js
const res = await fetch('https://conectacb.autonomiaydesarrollo.com/api/ruta', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    origen_texto: 'Cazuca',
    destino_texto: 'Juan Pablo II',
    usar_directo: false,
    hora: '07:30'
  })
});

if (res.status === 422) {
  const { detail } = await res.json(); // p. ej. "No pude ubicar el origen 'xyz'..."
  throw new Error(detail);
}
const ruta = await res.json();
if (ruta.tramos.length === 0) {
  // No hay servicio que conecte A y B a esa hora.
}
```

### Respuesta

| Campo | Tipo | Descripción |
| --- | --- | --- |
| `duracion_seg` | número | Tiempo total puerta a puerta: caminatas, esperas, recorridos y retrasos por novedades. |
| `distancia_m` | número | Distancia total. |
| `tarifa_total_cop` | número | Costo total en pesos, con la integración de tarifas ya aplicada (el segundo abordaje integrado seguido no se cobra). |
| `transbordos` | int | Número de transbordos. |
| `tramos` | lista | Los pasos del viaje, en orden. Vacía si no hay ruta. |
| `geometria` | GeoJSON `LineString` | Trazado completo del viaje. |
| `novedades` | lista | Alertas activas que afectan la ruta (derrumbes, obras, trancones…), con su retraso. |
| `informales_usadas` / `formales_usadas` | lista de ids | Líneas que usa la ruta. |
| `zonas` | lista | Zonas SITP por las que pasa. |
| `alternativas` | lista | Otra opción calculada sin la primera línea de la ruta principal, con la misma forma (sin su propio campo `alternativas`). Viene vacía si no existe o si es igual a la principal. |

Cada **tramo**:

| Campo | Descripción |
| --- | --- |
| `modo` | `acceso` (caminar), `informal`, `formal` (TransMilenio/SITP), `cable` (TransMiCable) o `directo` (carro). |
| `linea` | Id de la línea (`CB-07`, `TMC-01`…); `null` en caminatas. Nombre con `GET /lineas/{id}`. |
| `desde` / `hasta` | `{lat, lon}` donde empieza y termina el tramo. Ver [Problemas conocidos](#problemas-conocidos). |
| `duracion_seg` | Tiempo del recorrido (sin la espera). |
| `distancia_m` | Distancia del tramo. |
| `tarifa_cop` | Lo que se paga al abordar ese tramo. |
| `geometria` | GeoJSON `LineString` (o `Point` en caminatas de 0 m). |

> **Orden de coordenadas:** en `geometria` (GeoJSON) cada punto es **`[lon, lat]`**. En `origen`, `destino`, `desde` y `hasta` son objetos `{lat, lon}`.

Respuesta real de Cazucá a Juan Pablo II a las 07:30 (geometrías recortadas):

```json
{
  "distancia_m": 6718.5,
  "duracion_seg": 1655.8,
  "tarifa_total_cop": 7700.0,
  "transbordos": 1,
  "tramos": [
    {"modo": "acceso",   "linea": null,     "distancia_m": 507.0,  "duracion_seg": 380.3, "tarifa_cop": 0.0},
    {"modo": "informal", "linea": "CB-07",  "distancia_m": 4609.4, "duracion_seg": 638.2, "tarifa_cop": 4500.0},
    {"modo": "acceso",   "linea": null,     "distancia_m": 0.0,    "duracion_seg": 0.0,   "tarifa_cop": 0.0},
    {"modo": "cable",    "linea": "TMC-01", "distancia_m": 1602.1, "duracion_seg": 367.4, "tarifa_cop": 3200.0},
    {"modo": "acceso",   "linea": null,     "distancia_m": 0.0,    "duracion_seg": 0.0,   "tarifa_cop": 0.0}
  ],
  "zonas": [{"nombre": "Usme/Ciudad Bolivar", "letra": "H", "color": "Naranja"}],
  "informales_usadas": ["CB-07"],
  "formales_usadas": ["TMC-01"],
  "novedades": [],
  "alternativas": []
}
```

### Cómo mostrarla al usuario

- **Ignora las caminatas de 0 m** (`modo: "acceso"` con `distancia_m: 0`): marcan un transbordo en la misma parada.
- **Minutos:** `Math.round(duracion_seg / 60)`. Muestra la duración total arriba y la de cada tramo en la lista.
- **Nombre del tramo:** `GET /lineas/CB-07` devuelve `"Mototaxi Cazuca - Mirador del Paraiso"` y su `modo` (`mototaxi`, `colectivo`, `campero`, `buseta`, `cable`, `troncal`).
- **Tarifa:** `tarifa_total_cop` ya es el total a pagar; no sumes los `tarifa_cop` de los tramos.
- **Novedades:** muestra cada `novedades[i].titulo` y `retraso_seg / 60` minutos de retraso.
- **Hora de llegada:** hora de salida + `duracion_seg`.

## `POST /asistente` (texto libre)

Para chatbots: recibe la pregunta tal como la escribe el usuario, encuentra A y B, calcula la ruta y devuelve además una respuesta en texto.

```bash
curl -X POST https://conectacb.autonomiaydesarrollo.com/api/asistente \
  -H "Content-Type: application/json" \
  -d '{"texto": "como llego de Cazuca a Juan Pablo II", "usar_directo": false, "hora": "07:30"}'
```

```json
{
  "texto": "como llego de Cazuca a Juan Pablo II",
  "origen":  {"nombre": "Cazuca", "tipo": "barrio", "lat": 4.575, "lon": -74.18, "alias": ["cazuca", "altos de cazuca"]},
  "destino": {"nombre": "Juan Pablo II", "tipo": "estacion_cable", "lat": 4.555691, "lon": -74.147484, "alias": ["..."]},
  "respuesta": "Ruta de 21 min, tarifa $7,700. Camina, luego Mototaxi Cazuca - Mirador del Paraiso, luego camina, luego TransMiCable Tunal (Portal Tunal - Mirador del Paraiso), luego camina. 1 transbordo(s).",
  "ruta": { "...": "mismo formato que la respuesta de /ruta" }
}
```

| Campo | Tipo | Descripción |
| --- | --- | --- |
| `texto` | string | La pregunta. **Debe incluir el origen con "de" o "desde"**: `"de Quiba a Portal Tunal"`. Sin eso solo encuentra el destino. |
| `origen` / `destino` | `{lat, lon}` | Opcional: si el usuario compartió su ubicación, envíala aquí y el texto solo necesita el destino (`"a Portal Tunal"`). |
| `usar_directo` | bool | Por defecto `true`. Envía `false` para transporte público e informal. |
| `hora` / `dia` | string | Igual que en `/ruta`. |

Si no entiende el origen o el destino, responde **200** con `"ruta": null` y la explicación en `respuesta`:

```json
{"texto": "quiero ir a Portal Tunal", "origen": null, "destino": {"nombre": "Portal Tunal", "...": "..."},
 "respuesta": "No pude identificar el origen. Prueba con un barrio, vereda o estacion conocido.", "ruta": null}
```

## `POST /ruta/mapa` (para dibujar)

Misma petición que `/ruta`. Devuelve un GeoJSON `FeatureCollection` listo para Leaflet, Mapbox o Google Maps: un Feature por tramo con su `color` y los puntos de las novedades de la ruta.

```json
{
  "type": "FeatureCollection",
  "properties": {"duracion_seg": 1275.6, "tarifa_total_cop": 7700.0, "transbordos": 1},
  "features": [
    {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[-74.18, 4.575], "..."]},
     "properties": {"capa": "ruta", "modo": "informal", "linea": "CB-07", "color": "#F59E0B",
                    "distancia_m": 4609.4, "duracion_seg": 638.2, "tarifa_cop": 4500.0}}
  ]
}
```

Colores por modo: `cable` `#8B5CF6`, `formal` `#10B981`, `informal` `#F59E0B`, `acceso` `#9CA3AF`, `directo` `#2563EB`.
Las novedades llegan como Features con `"capa": "alerta"`.

## `GET /geocodificar` (buscar lugares)

```bash
curl "https://conectacb.autonomiaydesarrollo.com/api/geocodificar?q=tunal&limite=3"
```

```json
{"consulta": "tunal", "resultados": [
  {"nombre": "Portal Tunal", "tipo": "portal", "lat": 4.569675, "lon": -74.139249, "alias": ["portal tunal", "tunal", "estacion tunal"]}
]}
```

Busca primero en los 19 lugares conocidos de la localidad (barrios, veredas y estaciones). Si no encuentra, busca en OpenStreetMap, lo que sirve para direcciones y sitios de toda Bogotá (`q=Estadio El Campin`). Usa `externo=false` para buscar solo en los lugares conocidos, más rápido y sin salir a internet.

## Priorizar precio o transbordos

Por defecto gana la ruta más rápida. Con `pesos` se combina todo en un solo costo:
`costo = tiempo_seg × tiempo + tarifa_cop × tarifa + transbordos × transbordos`.

```json
"pesos": {"tiempo": 1, "tarifa": 0.5, "transbordos": 300}
```

Con ese ejemplo, cada $1.000 de tarifa pesa como 500 s de viaje y cada transbordo como 5 minutos.

## Cuando no hay ruta: errores y casos vacíos

| Situación | Respuesta | Qué mostrar |
| --- | --- | --- |
| No se encontró A o B por nombre | **422** `{"detail": "No pude ubicar el origen 'xyz'. Prueba con un lugar conocido o una direccion."}` | El `detail` tal cual; está escrito para el usuario. |
| Falta A o B | **422** `{"detail": "Falta el origen: envia coordenadas o 'origen_texto'."}` | Pedir el dato faltante. |
| No hay servicio que conecte A y B a esa hora (p. ej. 03:00) | **200** con `tramos: []`, `duracion_seg: 0` y `geometria` `Point [0, 0]` | "No encontramos ruta a esa hora"; sugerir otra hora. |
| Falla interna al calcular (red vial caída, etc.) | **502** `{"detail": "Error calculando la ruta: ..."}` | Mensaje genérico y reintentar. |
| `/asistente` no entiende el texto | **200** con `ruta: null` | El campo `respuesta`. |

## Restricciones en producción

- A través de `https://conectacb.autonomiaydesarrollo.com/api` solo se permiten `GET` y `POST`. `POST`, `PUT` y `DELETE` sobre `/alertas` están bloqueados porque la API aún no tiene autenticación para administrar alertas.
- No hay límite de peticiones todavía. La API usa el servidor público de OSRM (uso justo) para las caminatas y la ruta en carro; para mucho tráfico conviene alojar OSRM propio (`RUTAS_OSRM_BASE_URL`).
- La hora del servidor es la de Bogotá (`TZ=America/Bogota`).

## Problemas conocidos

- **Tramos en sentido contrario.** Cuando la ruta recorre una línea en el sentido opuesto al que está dibujada, `desde`, `hasta` y la `geometria` del tramo salen invertidos. Ejemplo: de Cazucá a Juan Pablo II, el tramo `TMC-01` va de Mirador del Paraíso a Juan Pablo II, pero la API lo devuelve de Juan Pablo II a Mirador. La duración, la distancia y la tarifa sí son correctas. Si generas instrucciones ("sube en…, baja en…"), toma la parada de subida del `hasta` del tramo anterior y la de bajada del `desde` del tramo siguiente, que siempre están en el orden del viaje.
- **`hora` no se valida.** Un valor como `"25:99"` no da error; valida el formato `HH:MM` antes de enviarlo.
- **Nombres sin tildes.** Los lugares y líneas vienen sin tildes ("Mirador del Paraiso", "Cazuca").
- **Formato de la tarifa en `respuesta`.** El texto del asistente usa coma de miles (`$7,700`); para mostrar precios usa `tarifa_total_cop` y dale formato colombiano (`$7.700`).
- **Datos de ejemplo.** El trazado del TransMiCable y sus estaciones son reales; las rutas informales, la troncal y las alertas son aproximadas o de prueba (ver `README.md`).
