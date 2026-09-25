"""API de ruteo multimodal para Bogota (zonas SITP + lineas + OSRM + novedades).

Todo se expone como API REST para que el frontend (web/WhatsApp) la consuma.
"""
from __future__ import annotations

import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .alertas import Alerta, almacen_alertas
from .cable import cargar_pilonas, pilonas_como_capa
from .config import settings
from .geocoder import Lugar, cargar_lugares, resolver_lugar
from .informal import LineaInformal, cargar_formales, cargar_informales
from .models import (
    Alerta as AlertaModel,
    AlertaCreate,
    AlertaUpdate,
    AsistenteRequest,
    AsistenteResponse,
    Coordenada,
    GeocodificacionResponse,
    LugarResumen,
    RutaRequest,
    RutaResponse,
    ZonaResumen,
    ZonaUbicacionResponse,
)
from .routing import calcular_ruta
from .tarifas import cargar_tarifas
from .tiempo import dia_letra, hora_actual
from .zones import cargar_zonas

COLORES_MODO = {
    "cable": "#8B5CF6",
    "formal": "#10B981",
    "informal": "#F59E0B",
    "acceso": "#9CA3AF",
    "directo": "#2563EB",
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    cargar_zonas()
    cargar_informales()
    cargar_formales()
    cargar_lugares()
    cargar_tarifas()
    cargar_pilonas()
    almacen_alertas()
    yield


app = FastAPI(
    title="ConectaCB API",
    description=(
        "Ruteo multimodal para Ciudad Bolivar: red vial (OSRM), TransMiCable/SITP, "
        "colectivos y rutas veredales, con novedades en vivo, horarios y tarifas."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _todas_lineas() -> list[LineaInformal]:
    return cargar_formales().lineas + cargar_informales().lineas


def _linea_por_id(id_linea: str) -> LineaInformal | None:
    return cargar_formales().por_id(id_linea) or cargar_informales().por_id(id_linea)


_NOMBRE_MODO = {"alimentador": "el alimentador", "troncal": "el TransMilenio", "sitp": "el SITP"}


def _paso_linea(tramo) -> str:
    """Instruccion de un tramo en bus o cable, con el codigo y los paraderos si vienen del GTFS."""
    lin = _linea_por_id(tramo.linea)
    if lin is None:
        return tramo.linea
    if not tramo.codigo:
        return lin.nombre
    texto = f"toma {_NOMBRE_MODO.get(lin.modo, 'la ruta')} {tramo.codigo}"
    # El GTFS nombra los alimentadores "Barrio || Portal": se muestra "Barrio - Portal".
    destino = " - ".join(p.strip() for p in (lin.propiedades.get("destino") or "").split("||") if p.strip())
    if destino:
        texto += f" ({destino})"
    if tramo.parada_desde:
        texto += f" en {tramo.parada_desde}"
    if tramo.parada_hasta:
        texto += f" y bajate en {tramo.parada_hasta}"
    return texto


def _zona_geometria(zona) -> dict:
    return {"type": "MultiPolygon", "coordinates": zona.multipoligono}


def _alerta_publica(a: Alerta) -> dict:
    """Alerta con las lineas a las que el ruteo realmente la aplica (misma regla que routing)."""
    radio = settings.alerta_radio_afectacion_m
    efectivas = [lin.id for lin in _todas_lineas() if a.afecta_linea(lin, radio)]
    return {**a.a_dict(), "lineas_afectadas_efectivas": efectivas}


def _alerta_feature(a: Alerta) -> dict:
    return {
        "type": "Feature",
        "geometry": a.geometria,
        "properties": {
            "capa": "alerta",
            "id": a.id,
            "tipo": a.tipo,
            "titulo": a.titulo,
            "severidad": a.severidad,
            "retraso_seg": a.retraso_seg,
            "lineas_afectadas": a.lineas_afectadas,
            "lineas_afectadas_efectivas": _alerta_publica(a)["lineas_afectadas_efectivas"],
            "color": {"alta": "#DC2626", "media": "#F59E0B", "baja": "#FACC15"}.get(
                a.severidad, "#F59E0B"
            ),
        },
    }


def _resumir_ruta(resp: RutaResponse) -> str:
    if not resp.tramos:
        return "No encontre una ruta disponible con esas opciones y ese horario."
    minutos = max(1, round(resp.duracion_seg / 60))
    pasos: list[tuple[str, str]] = []
    for tramo in resp.tramos:
        if tramo.modo in {"cable", "formal", "informal"} and tramo.linea:
            pasos.append(("linea", _paso_linea(tramo)))
        elif tramo.modo == "directo":
            pasos.append(("accion", "ve por la via directa"))
        elif tramo.modo == "acceso":
            pasos.append(("accion", "camina"))
    # Colapsa acciones repetidas consecutivas (p. ej. caminar-caminar).
    compacto: list[tuple[str, str]] = []
    for paso in pasos:
        if compacto and paso[0] == "accion" and compacto[-1] == paso:
            continue
        compacto.append(paso)
    secuencia = ", luego ".join(p[1] for p in compacto)
    tarifa = f"{int(resp.tarifa_total_cop):,}".replace(",", ".")  # formato colombiano: $3.550
    texto = f"Ruta de {minutos} min, tarifa ${tarifa}."
    if secuencia:
        texto += f" {secuencia[0].upper()}{secuencia[1:]}."
    if resp.transbordos:
        texto += f" {resp.transbordos} transbordo(s)."
    if resp.novedades:
        avisos = "; ".join(f"{n.titulo} (+{round(n.retraso_seg / 60)} min)" for n in resp.novedades)
        texto += f" Novedades: {avisos}."
    return texto


def _parsear_texto(texto: str) -> tuple[str | None, str | None]:
    """Devuelve (origen_texto, destino_texto) desde lenguaje natural."""
    t = (texto or "").strip()
    # "de X a Y", "desde el X hasta la Y", "voy de X al Y", "del X pa' Y"...
    destino = r"(?:a|al|hasta|para|pa'?|hacia)(?:\s+(?:el|la|los|las))?"
    m = re.search(
        rf"\b(?:de|desde|del)(?:\s+(?:el|la|los|las))?\s+(.+?)\s+{destino}\s+(.+?)\s*[?.!]*$",
        t,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m2 = re.search(rf"\b{destino}\s+(.+?)\s*[?.!]*$", t, re.IGNORECASE)
    if m2:
        return None, m2.group(1).strip()
    return None, None


def _preparar_ruta(req: RutaRequest) -> RutaRequest:
    """Completa origen/destino desde texto (gazetteer local + OSM) si hacen falta."""
    gaz = cargar_lugares()
    externo = settings.geocoder_externo

    def resolver(coord: Coordenada | None, texto: str | None, nombre: str) -> Coordenada:
        if coord is not None:
            return coord
        if texto:
            lugar = resolver_lugar(texto, gaz, externo)
            if lugar is not None:
                return Coordenada(lat=lugar.lat, lon=lugar.lon)
            raise HTTPException(
                status_code=422,
                detail=f"No pude ubicar el {nombre} '{texto}'. Prueba con un lugar conocido o una direccion.",
            )
        raise HTTPException(
            status_code=422,
            detail=f"Falta el {nombre}: envia coordenadas o '{nombre}_texto'.",
        )

    req.origen = resolver(req.origen, req.origen_texto, "origen")
    req.destino = resolver(req.destino, req.destino_texto, "destino")
    return req


# --------------------------------------------------------------------------
# Sistema
# --------------------------------------------------------------------------
@app.get("/health", tags=["sistema"])
def health() -> dict:
    return {
        "status": "ok",
        "version": "2.0.0",
        "zonas": len(cargar_zonas().zonas),
        "rutas_informales": len(cargar_informales().lineas),
        "rutas_formales": len(cargar_formales().lineas),
        "pilonas_cable": len(cargar_pilonas().get("features", [])),
        "lugares": len(cargar_lugares().lugares),
        "alertas": len(almacen_alertas().listar()),
        "osrm": settings.osrm_base_url,
        "hora_servidor": hora_actual(),
        "dia_servidor": dia_letra(),
    }


# --------------------------------------------------------------------------
# Zonas SITP
# --------------------------------------------------------------------------
@app.get("/zonas", tags=["zonas"])
def listar_zonas() -> dict:
    return cargar_zonas().geojson_crudo


@app.get("/zonas/ubicacion", response_model=ZonaUbicacionResponse, tags=["zonas"])
def zona_en_ubicacion(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radio_m: float = Query(2000.0, ge=0, le=50000),
) -> ZonaUbicacionResponse:
    catalogo = cargar_zonas()
    zona = catalogo.zona_en_punto(lon, lat)
    cercanas = catalogo.zonas_cercanas(lon, lat, radio_m)
    return ZonaUbicacionResponse(
        punto=Coordenada(lat=lat, lon=lon),
        zona=ZonaResumen(**zona.resumen()) if zona else None,
        zonas_cercanas=[ZonaResumen(**z.resumen()) for z in cercanas],
    )


# --------------------------------------------------------------------------
# Lineas (formales + informales)
# --------------------------------------------------------------------------
@app.get("/rutas-informales", tags=["lineas"])
def listar_informales() -> dict:
    catalogo = cargar_informales()
    return {"total": len(catalogo.lineas), "rutas": [l.resumen() for l in catalogo.lineas]}


@app.get("/rutas-formales", tags=["lineas"])
def listar_formales() -> dict:
    catalogo = cargar_formales()
    return {"total": len(catalogo.lineas), "rutas": [l.resumen() for l in catalogo.lineas]}


@app.get("/lineas", tags=["lineas"])
def listar_lineas(
    geometria: bool = Query(True, description="Incluir el trazado de cada linea (la respuesta pesa varios MB con el SITP)."),
    modo: str | None = Query(None, description="Filtrar por modo: cable, troncal, alimentador, sitp, colectivo..."),
    codigo: str | None = Query(None, description="Filtrar por codigo del SITP, p. ej. '6-3'."),
) -> dict:
    lineas = [
        l for l in _todas_lineas()
        if (modo is None or l.modo == modo) and (codigo is None or (l.codigo or "").lower() == codigo.lower())
    ]
    return {"total": len(lineas), "lineas": [l.resumen(geometria=geometria) for l in lineas]}


@app.get("/lineas/{id_linea}", tags=["lineas"])
def obtener_linea(id_linea: str) -> dict:
    lin = _linea_por_id(id_linea)
    if lin is None:
        raise HTTPException(status_code=404, detail=f"Linea {id_linea} no encontrada")
    return lin.resumen()


@app.get("/lineas/{id_linea}/horario", tags=["horarios"])
def horario_linea(
    id_linea: str,
    hora: str | None = Query(None, description="HH:MM; por defecto la hora actual"),
    dia: str | None = Query(None, description="L,M,X,J,V,S,D"),
) -> dict:
    lin = _linea_por_id(id_linea)
    if lin is None:
        raise HTTPException(status_code=404, detail=f"Linea {id_linea} no encontrada")
    h = hora or hora_actual()
    d = dia or dia_letra()
    return {
        "id": lin.id,
        "nombre": lin.nombre,
        "horario": lin.horario,
        "frecuencia_min": lin.frecuencia_min,
        "hora_consultada": h,
        "dia_consultado": d,
        "activo": lin.activo(h, d),
        "espera_seg": round(lin.espera_seg(h, d), 1),
    }


@app.get("/horarios", tags=["horarios"])
def horarios(
    hora: str | None = Query(None),
    dia: str | None = Query(None),
) -> dict:
    h = hora or hora_actual()
    d = dia or dia_letra()
    salida = []
    for lin in _todas_lineas():
        salida.append(
            {
                "id": lin.id,
                "nombre": lin.nombre,
                "tipo": lin.tipo,
                "horario": lin.horario,
                "frecuencia_min": lin.frecuencia_min,
                "activo": lin.activo(h, d),
                "espera_seg": round(lin.espera_seg(h, d), 1),
            }
        )
    return {"hora_consultada": h, "dia_consultado": d, "total": len(salida), "lineas": salida}


@app.get("/tarifas", tags=["tarifas"])
def tarifas() -> dict:
    conf = cargar_tarifas()
    lineas = [
        {"id": l.id, "nombre": l.nombre, "modo": l.modo, "tarifa": l.tarifa, "integrado": l.es_integrado()}
        for l in _todas_lineas()
    ]
    return {**conf, "lineas": lineas}


# --------------------------------------------------------------------------
# Geocoding / lugares
# --------------------------------------------------------------------------
@app.get("/lugares", tags=["geocoding"])
def listar_lugares() -> dict:
    lugares = cargar_lugares().listar()
    return {"total": len(lugares), "lugares": [l.resumen() for l in lugares]}


@app.get("/geocodificar", response_model=GeocodificacionResponse, tags=["geocoding"])
def geocodificar(
    q: str = Query(..., min_length=2),
    limite: int = Query(5, ge=1, le=20),
    externo: bool = Query(True, description="Si el gazetteer local no encuentra, buscar en OSM (Photon)."),
) -> GeocodificacionResponse:
    resultados = cargar_lugares().buscar(q, limite=limite)
    if not resultados and externo and settings.geocoder_externo:
        from .geocoder_externo import buscar_externo

        externos = buscar_externo(q, limite=limite)
        return GeocodificacionResponse(
            consulta=q,
            resultados=[
                LugarResumen(nombre=l.nombre, tipo=l.tipo, lat=l.lat, lon=l.lon, alias=l.alias)
                for l in externos
            ],
        )
    return GeocodificacionResponse(
        consulta=q,
        resultados=[
            LugarResumen(nombre=l.nombre, tipo=l.tipo, lat=l.lat, lon=l.lon, alias=l.alias)
            for _, l in resultados
        ],
    )


# --------------------------------------------------------------------------
# Alertas / novedades
# --------------------------------------------------------------------------
@app.get("/alertas", response_model=list[AlertaModel], tags=["alertas"])
def listar_alertas(
    activas: bool | None = Query(None),
    tipo: str | None = Query(None),
    solo_vigentes: bool = Query(False),
) -> list[dict]:
    return [
        _alerta_publica(a)
        for a in almacen_alertas().listar(activas=activas, tipo=tipo, solo_vigentes=solo_vigentes)
    ]


@app.get("/alertas/cerca", response_model=list[AlertaModel], tags=["alertas"])
def alertas_cerca(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radio_m: float = Query(1500.0, ge=0, le=50000),
) -> list[dict]:
    return [_alerta_publica(a) for a in almacen_alertas().cerca(lon, lat, radio_m)]


@app.get("/alertas/{id_alerta}", response_model=AlertaModel, tags=["alertas"])
def obtener_alerta(id_alerta: str) -> dict:
    alerta = almacen_alertas().obtener(id_alerta)
    if alerta is None:
        raise HTTPException(status_code=404, detail=f"Alerta {id_alerta} no encontrada")
    return _alerta_publica(alerta)


@app.post("/alertas", response_model=AlertaModel, status_code=201, tags=["alertas"])
def crear_alerta(datos: AlertaCreate) -> dict:
    return _alerta_publica(almacen_alertas().crear(datos.model_dump()))


@app.put("/alertas/{id_alerta}", response_model=AlertaModel, tags=["alertas"])
def actualizar_alerta(id_alerta: str, datos: AlertaUpdate) -> dict:
    alerta = almacen_alertas().actualizar(id_alerta, datos.model_dump(exclude_unset=True))
    if alerta is None:
        raise HTTPException(status_code=404, detail=f"Alerta {id_alerta} no encontrada")
    return _alerta_publica(alerta)


@app.delete("/alertas/{id_alerta}", tags=["alertas"])
def eliminar_alerta(id_alerta: str) -> dict:
    if not almacen_alertas().eliminar(id_alerta):
        raise HTTPException(status_code=404, detail=f"Alerta {id_alerta} no encontrada")
    return {"eliminado": id_alerta}


# --------------------------------------------------------------------------
# Ruteo
# --------------------------------------------------------------------------
@app.post("/ruta", response_model=RutaResponse, tags=["ruteo"])
def calcular(req: RutaRequest) -> RutaResponse:
    req = _preparar_ruta(req)
    try:
        principal, alternativas = calcular_ruta(req)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Error calculando la ruta: {exc}") from exc
    return RutaResponse(**principal.model_dump(), alternativas=alternativas)


@app.post("/ruta/mapa", tags=["mapa"])
def ruta_mapa(req: RutaRequest) -> dict:
    """Ruta como FeatureCollection por tramos (colores por modo) + novedades."""
    req = _preparar_ruta(req)
    try:
        principal, _ = calcular_ruta(req)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Error calculando la ruta: {exc}") from exc

    features: list[dict] = []
    for tramo in principal.tramos:
        features.append(
            {
                "type": "Feature",
                "geometry": tramo.geometria,
                "properties": {
                    "capa": "ruta",
                    "modo": tramo.modo,
                    "linea": tramo.linea,
                    "codigo": tramo.codigo,
                    "parada_desde": tramo.parada_desde,
                    "parada_hasta": tramo.parada_hasta,
                    "color": COLORES_MODO.get(tramo.modo, "#111827"),
                    "distancia_m": tramo.distancia_m,
                    "duracion_seg": tramo.duracion_seg,
                    "tarifa_cop": tramo.tarifa_cop,
                },
            }
        )
    for nov in principal.novedades:
        alerta = almacen_alertas().obtener(nov.id)
        if alerta and alerta.geometria:
            features.append(_alerta_feature(alerta))
    return {
        "type": "FeatureCollection",
        "properties": {
            "duracion_seg": principal.duracion_seg,
            "tarifa_total_cop": principal.tarifa_total_cop,
            "transbordos": principal.transbordos,
        },
        "features": features,
    }


@app.get("/cable/pilonas", tags=["mapa"])
def cable_pilonas() -> dict:
    """Pilonas del TransMiCable (trazado real) como FeatureCollection."""
    return cargar_pilonas()


@app.get("/capas", tags=["mapa"])
def capas(
    incluir_zonas: bool = Query(True),
    incluir_lineas: bool = Query(True),
    incluir_alertas: bool = Query(True),
    incluir_pilonas: bool = Query(True),
    incluir_sitp: bool = Query(
        False, description="Incluir las ~400 rutas del SITP (GTFS). Por defecto no: la respuesta pasa de 20 KB a varios MB."
    ),
) -> dict:
    """Capas base para el mapa: zonas SITP + lineas + alertas + pilonas del cable."""
    features: list[dict] = []
    if incluir_zonas:
        for z in cargar_zonas().zonas:
            features.append(
                {
                    "type": "Feature",
                    "geometry": _zona_geometria(z),
                    "properties": {"capa": "zona", **z.resumen()},
                }
            )
    if incluir_lineas:
        for lin in _todas_lineas():
            if lin.codigo and not incluir_sitp:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [list(p) for p in lin.geometria]},
                    "properties": {
                        "capa": "linea",
                        "id": lin.id,
                        "nombre": lin.nombre,
                        "codigo": lin.codigo,
                        "tipo": lin.tipo,
                        "modo": lin.modo,
                        "tarifa": lin.tarifa,
                    },
                }
            )
    if incluir_alertas:
        for a in almacen_alertas().listar(solo_vigentes=True):
            if a.geometria:
                features.append(_alerta_feature(a))
    if incluir_pilonas:
        features.extend(pilonas_como_capa())
    return {"type": "FeatureCollection", "features": features}


# --------------------------------------------------------------------------
# Asistente en lenguaje natural
# --------------------------------------------------------------------------
@app.post("/asistente", response_model=AsistenteResponse, tags=["asistente"])
def asistente(req: AsistenteRequest) -> AsistenteResponse:
    gaz = cargar_lugares()
    origen_txt, destino_txt = _parsear_texto(req.texto)

    lugar_origen: Lugar | None = None
    lugar_destino: Lugar | None = None

    if req.origen is not None:
        coord_origen = (req.origen.lon, req.origen.lat)
    elif origen_txt:
        lugar_origen = resolver_lugar(origen_txt, gaz, settings.geocoder_externo)
        coord_origen = (lugar_origen.lon, lugar_origen.lat) if lugar_origen else None
    else:
        coord_origen = None

    if req.destino is not None:
        coord_destino = (req.destino.lon, req.destino.lat)
    elif destino_txt:
        lugar_destino = resolver_lugar(destino_txt, gaz, settings.geocoder_externo)
        coord_destino = (lugar_destino.lon, lugar_destino.lat) if lugar_destino else None
    else:
        coord_destino = None

    if coord_origen is None or coord_destino is None:
        faltante = "origen" if coord_origen is None else "destino"
        return AsistenteResponse(
            texto=req.texto,
            origen=LugarResumen(**lugar_origen.resumen()) if lugar_origen else None,
            destino=LugarResumen(**lugar_destino.resumen()) if lugar_destino else None,
            respuesta=f"No pude identificar el {faltante}. Prueba con un barrio, vereda o estacion conocido.",
            ruta=None,
        )

    ruta_req = RutaRequest(
        origen=Coordenada(lat=coord_origen[1], lon=coord_origen[0]),
        destino=Coordenada(lat=coord_destino[1], lon=coord_destino[0]),
        perfil=req.perfil,
        usar_directo=req.usar_directo,
        hora=req.hora,
        dia=req.dia,
    )
    principal, alternativas = calcular_ruta(ruta_req)
    respuesta = RutaResponse(**principal.model_dump(), alternativas=alternativas)
    return AsistenteResponse(
        texto=req.texto,
        origen=LugarResumen(**lugar_origen.resumen()) if lugar_origen else None,
        destino=LugarResumen(**lugar_destino.resumen()) if lugar_destino else None,
        respuesta=_resumir_ruta(respuesta),
        ruta=respuesta,
    )
