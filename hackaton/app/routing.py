"""Ruteo multimodal: red vial (OSRM) + SITP (GTFS de TransMilenio) + TransMiCable + informales.

El grafo se genera sobre la marcha mientras corre la busqueda (A*), solo en la region del viaje:
- paraderos fisicos: las rutas del SITP que paran en el mismo paradero lo comparten;
- estados "a bordo" de una linea en una de sus paradas;
- aristas de caminar (acceso y transbordo), abordar (espera + tarifa), recorrer hasta la
  siguiente parada y bajar.
El costo es lexicografico (tiempo, tarifa, transbordos) o ponderado si el request envia `pesos`.

Se integran ademas:
- salidas programadas del GTFS (espera real segun la hora) y horarios de las demas lineas,
- tarifas integradas del SITP (troncal, zonal, alimentador y TransMiCable),
- novedades/alertas en vivo (retrasos que afectan el costo).
"""
from __future__ import annotations

import heapq
import itertools
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterator

from . import geo
from .alertas import Alerta, AlmacenAlertas, almacen_alertas
from .config import settings
from .geo import Punto
from .informal import CatalogoInformales, LineaInformal, cargar_formales, cargar_informales
from .models import Coordenada, NovedadResumen, RutaRequest, RutaResumen, Tramo, ZonaResumen
from .osrm import OSRMClient, RutaOSRM, cliente_osrm
from .tarifas import cargar_tarifas
from .tiempo import dia_letra, hora_actual, parse_hora
from .zones import CatalogoZonas, cargar_zonas

# (nodo, linea a bordo|None, integrado: 0/1, abordajes hechos)
Estado = tuple[str, str | None, int, int]

INICIO: Estado = ("O", None, 0, 0)

# Velocidad maxima para la cota optimista de A* (ningun modo va mas rapido en promedio).
_VEL_MAX_MS = 80 / 3.6
# Cuanto se puede alejar el viaje del recuadro origen-destino.
_MARGEN_REGION_M = 2500.0
# Costo extra de cada abordaje en el orden por tiempo (no cambia la duracion informada).
PENALIDAD_ABORDAJE_SEG = 300.0


def _seg_caminata(dist_m: float, vel_kmh: float) -> float:
    return dist_m / (vel_kmh * 1000.0 / 3600.0)


def _cero(pesos):
    return (0.0, 0.0, 0) if pesos is None else 0.0


def _costo(dt: float, dfare: float, dtrans: float, pesos):
    if pesos is None:
        # Cada abordaje pesa unos minutos mas que su espera: sin esto, la ruta "mas rapida" cambia
        # de bus para ganar un minuto. No se suma a la duracion que se informa.
        return (dt + PENALIDAD_ABORDAJE_SEG * dtrans, dfare, int(dtrans))
    return pesos.tiempo * dt + pesos.tarifa * dfare + pesos.transbordos * dtrans


def _add(a, b):
    if isinstance(a, tuple):
        return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
    return a + b


def _hora_mas(hora: str, segundos: float) -> str:
    base = parse_hora(hora)
    if base is None:
        return hora
    total = int(base + segundos / 60.0) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _novedad(alerta: Alerta) -> dict:
    return {
        "id": alerta.id,
        "tipo": alerta.tipo,
        "titulo": alerta.titulo,
        "severidad": alerta.severidad,
        "retraso_seg": alerta.retraso_seg,
        "lineas_afectadas": alerta.lineas_afectadas,
    }


class _Arista:
    __slots__ = ("destino", "dt", "dfare", "dtrans", "meta")

    def __init__(self, destino: Estado, dt: float, dfare: float, dtrans: float, meta: dict):
        self.destino = destino
        self.dt = dt
        self.dfare = dfare
        self.dtrans = dtrans
        self.meta = meta


@dataclass
class Contexto:
    zonas: CatalogoZonas
    informales: CatalogoInformales
    formales: CatalogoInformales
    osrm: OSRMClient
    alertas: AlmacenAlertas
    tarifas: dict
    hora: str
    dia: str


def _arista_acceso(origen: Punto, destino: Punto, estado_destino: Estado, dist: float | None = None) -> _Arista:
    if dist is None:
        dist = geo.haversine_m(origen[1], origen[0], destino[1], destino[0])
    dt = _seg_caminata(dist, settings.velocidad_caminata_kmh)
    meta = {
        "tipo": "acceso",
        "linea": None,
        "distancia_m": dist,
        "geometria": [origen, destino],
    }
    return _Arista(estado_destino, dt, 0.0, 0.0, meta)


class _Grilla:
    """Indice espacial simple de paraderos para buscar vecinos por radio."""

    def __init__(self, puntos: dict[str, Punto], celda_m: float):
        self.celda_m = max(celda_m, 50.0)
        self.celda = self.celda_m / 111320.0
        self.puntos = puntos
        self.celdas: dict[tuple[int, int], list[str]] = defaultdict(list)
        for clave, p in puntos.items():
            self.celdas[self._celda(p)].append(clave)

    def _celda(self, p: Punto) -> tuple[int, int]:
        return int(math.floor(p[0] / self.celda)), int(math.floor(p[1] / self.celda))

    def cerca(self, p: Punto, radio_m: float) -> list[tuple[str, float]]:
        cx, cy = self._celda(p)
        n = int(math.ceil(radio_m / self.celda_m))
        salida = []
        for dx in range(-n, n + 1):
            for dy in range(-n, n + 1):
                for clave in self.celdas.get((cx + dx, cy + dy), ()):
                    q = self.puntos[clave]
                    d = geo.haversine_m(p[1], p[0], q[1], q[0])
                    if d <= radio_m:
                        salida.append((clave, d))
        return salida


class _Red:
    """Red de transporte de una consulta: lineas y paraderos en la region del viaje."""

    def __init__(self, req: RutaRequest, ctx: Contexto, prohibidas: set[str]):
        self.req = req
        self.ctx = ctx
        self.o: Punto = (req.origen.lon, req.origen.lat)
        self.d: Punto = (req.destino.lon, req.destino.lat)
        self.radio = req.opciones.radio_acceso_m
        self.radio_transbordo = settings.radio_transbordo_m
        self.max_abordajes = req.opciones.max_transbordos + 1
        self.tipos_integrados = set(ctx.tarifas.get("tipos_integrados") or [])
        self.directo: _Arista | None = None

        candidatas: list[LineaInformal] = []
        if req.usar_informales:
            candidatas.extend(ctx.informales.lineas)
        if req.usar_formales:
            candidatas.extend(ctx.formales.lineas)

        region = geo.bbox_expandida(geo.bbox([self.o, self.d]), max(self.radio, _MARGEN_REGION_M))
        self.lineas: dict[str, LineaInformal] = {}
        self.indices: dict[str, list[int]] = {}
        self._posicion: dict[str, dict[int, int]] = {}
        self.pos: dict[str, Punto] = {}
        self.abordajes: dict[str, list[tuple[LineaInformal, int]]] = defaultdict(list)
        for lin in candidatas:
            if lin.id in prohibidas or lin.grupo in prohibidas:
                continue
            idxs = [i for i, p in enumerate(lin.paradas) if geo._en_bbox(p[0], p[1], region)]
            if not idxs:
                continue
            self.lineas[lin.id] = lin
            self.indices[lin.id] = idxs
            self._posicion[lin.id] = {i: n for n, i in enumerate(idxs)}
            for i in idxs:
                clave = lin.clave_parada(i)
                self.pos.setdefault(clave, lin.paradas[i])
                self.abordajes[clave].append((lin, i))

        self.grilla = _Grilla(self.pos, self.radio_transbordo)
        self.cerca_destino = dict(self.grilla.cerca(self.d, self.radio))
        self._vecinos: dict[str, list[tuple[str, float]]] = {}
        self._alertas: dict[str, list[Alerta]] = {}

    # --- apoyo ---------------------------------------------------------------
    def _alertas_linea(self, lin: LineaInformal) -> list[Alerta]:
        if lin.id not in self._alertas:
            self._alertas[lin.id] = self.ctx.alertas.activas_para_linea(lin)
        return self._alertas[lin.id]

    def _vecinos_de(self, clave: str) -> list[tuple[str, float]]:
        if clave not in self._vecinos:
            self._vecinos[clave] = [
                (k, d) for k, d in self.grilla.cerca(self.pos[clave], self.radio_transbordo) if k != clave
            ]
        return self._vecinos[clave]

    def _hora(self, g) -> str:
        # En modo lexicografico el primer componente del costo es el tiempo transcurrido
        # (mas la penalidad de los abordajes, que se descuenta).
        if isinstance(g, tuple):
            return _hora_mas(self.ctx.hora, g[0] - PENALIDAD_ABORDAJE_SEG * g[2])
        return self.ctx.hora

    def posicion(self, estado: Estado) -> Punto:
        nodo, linea = estado[0], estado[1]
        if nodo == "O":
            return self.o
        if nodo == "D":
            return self.d
        if linea is not None:
            return self.lineas[linea].paradas[int(nodo.rsplit("#", 1)[1])]
        return self.pos[nodo]

    def cota(self, estado: Estado) -> float:
        """Tiempo minimo posible hasta el destino (en linea recta a la velocidad maxima)."""
        p = self.posicion(estado)
        return geo.haversine_m(p[1], p[0], self.d[1], self.d[0]) / _VEL_MAX_MS

    # --- aristas -------------------------------------------------------------
    def aristas(self, estado: Estado, g) -> Iterator[_Arista]:
        nodo, linea, flag, abordajes = estado
        if nodo == "O":
            if self.directo is not None:
                yield self.directo
            for clave, dist in self.grilla.cerca(self.o, self.radio):
                yield _arista_acceso(self.o, self.pos[clave], (clave, None, 0, 0), dist)
            return

        if linea is None:
            yield from self._desde_paradero(nodo, flag, abordajes, g)
        else:
            yield from self._a_bordo(nodo, linea, flag, abordajes)

    def _desde_paradero(self, clave: str, flag: int, abordajes: int, g) -> Iterator[_Arista]:
        p = self.pos[clave]
        if clave in self.cerca_destino:
            yield _arista_acceso(p, self.d, ("D", None, flag, abordajes), self.cerca_destino[clave])
        # Transbordo a pie a otro paradero cercano (antes del primer bus basta con el acceso desde O).
        if abordajes > 0:
            for otra, dist in self._vecinos_de(clave):
                yield _arista_acceso(p, self.pos[otra], (otra, None, flag, abordajes), dist)
        if abordajes >= self.max_abordajes:
            return
        hora = self._hora(g)
        for lin, i in self.abordajes[clave]:
            idxs = self.indices[lin.id]
            if lin.sentido_unico and i == idxs[-1]:
                continue  # ultima parada: no hay a donde ir
            if not lin.activo(hora, self.ctx.dia, i):
                continue
            integrado = lin.es_integrado(self.tipos_integrados)
            alertas = self._alertas_linea(lin)
            retraso = max((a.retraso_seg for a in alertas), default=0.0)
            espera = lin.espera_seg(hora, self.ctx.dia, i)
            # Tarifa integrada: con el pasaje ya pagado, el siguiente abordaje integrado no cobra.
            fare = 0.0 if (integrado and flag == 1) else lin.tarifa
            nuevo_flag = 1 if integrado else flag
            yield _Arista(
                (f"{lin.id}#{i}", lin.id, nuevo_flag, abordajes + 1),
                espera + retraso,
                fare,
                1.0,
                {
                    "tipo": "abordar",
                    "linea": lin.id,
                    "linea_tipo": lin.tipo,
                    "tarifa_cop": fare,
                    "espera_seg": espera,
                    "alertas": [_novedad(a) for a in alertas],
                    "distancia_m": 0.0,
                    "geometria": [],
                },
            )

    def _a_bordo(self, nodo: str, id_linea: str, flag: int, abordajes: int) -> Iterator[_Arista]:
        lin = self.lineas[id_linea]
        i = int(nodo.rsplit("#", 1)[1])
        yield _Arista(
            (lin.clave_parada(i), None, flag, abordajes),
            0.0,
            0.0,
            0.0,
            {"tipo": "bajar", "linea": lin.id, "linea_tipo": lin.tipo, "distancia_m": 0.0, "geometria": []},
        )
        idxs = self.indices[id_linea]
        n = self._posicion[id_linea][i]
        siguientes = [idxs[n + 1]] if n + 1 < len(idxs) else []
        if not lin.sentido_unico and n > 0:
            siguientes.append(idxs[n - 1])
        for j in siguientes:
            geom, dist, dur = lin.tramo(i, j)
            yield _Arista(
                (f"{id_linea}#{j}", id_linea, flag, abordajes),
                dur,
                0.0,
                0.0,
                {
                    "tipo": "informal",
                    "linea": lin.id,
                    "linea_tipo": lin.tipo,
                    "codigo": lin.codigo,
                    "desde_idx": i,
                    "hasta_idx": j,
                    "parada_desde": lin.nombre_parada(i),
                    "parada_hasta": lin.nombre_parada(j),
                    "distancia_m": dist,
                    "geometria": geom,
                },
            )


def _construir_red(req: RutaRequest, ctx: Contexto, prohibidas: set[str] | None = None) -> tuple[_Red, RutaOSRM]:
    red = _Red(req, ctx, prohibidas or set())
    o, d = red.o, red.d
    if req.usar_directo:
        # Ruta directa O->D por la red vial (OSRM).
        ruta_directa = ctx.osrm.ruta(o, d, req.perfil)
        alertas_directo = ctx.alertas.activas_para_geometria(ruta_directa.geometria)
        retraso = max((a.retraso_seg for a in alertas_directo), default=0.0)
        red.directo = _Arista(
            ("D", None, 0, 0),
            ruta_directa.duracion_seg + retraso,
            0.0,
            0.0,
            {
                "tipo": "directo",
                "linea": None,
                "distancia_m": ruta_directa.distancia_m,
                "geometria": ruta_directa.geometria,
                "aprox": ruta_directa.aprox,
                "alertas": [_novedad(a) for a in alertas_directo],
            },
        )
    else:
        ruta_directa = OSRMClient._respaldo(o, d, req.perfil)
    return red, ruta_directa


def _prioridad(g, cota: float, pesos):
    if pesos is None:
        return (g[0] + cota, g[1], g[2])
    return g + pesos.tiempo * cota


def _buscar(red: _Red, pesos) -> list[_Arista] | None:
    """A* desde el origen hasta el destino."""
    costos: dict[Estado, Any] = {INICIO: _cero(pesos)}
    prev: dict[Estado, tuple[Estado, _Arista]] = {}
    cerrados: set[Estado] = set()
    contador = itertools.count()
    pq = [(_prioridad(_cero(pesos), red.cota(INICIO), pesos), next(contador), INICIO)]
    while pq:
        _, _, estado = heapq.heappop(pq)
        if estado in cerrados:
            continue
        cerrados.add(estado)
        if estado[0] == "D":
            return _reconstruir(prev, estado)
        g = costos[estado]
        for ar in red.aristas(estado, g):
            if ar.destino in cerrados:
                continue
            nc = _add(g, _costo(ar.dt, ar.dfare, ar.dtrans, pesos))
            actual = costos.get(ar.destino)
            if actual is None or nc < actual:
                costos[ar.destino] = nc
                prev[ar.destino] = (estado, ar)
                heapq.heappush(pq, (_prioridad(nc, red.cota(ar.destino), pesos), next(contador), ar.destino))
    return None


def _reconstruir(prev, objetivo: Estado) -> list[_Arista]:
    aristas: list[_Arista] = []
    estado = objetivo
    while estado in prev:
        anterior, ar = prev[estado]
        aristas.append(ar)
        estado = anterior
    aristas.reverse()
    return aristas


def _geometria_unica(puntos: list[Punto]) -> list[Punto]:
    salida: list[Punto] = []
    for p in puntos:
        if not salida or salida[-1] != p:
            salida.append(p)
    return salida


def _fusionar_tramos(brutos: list[dict]) -> list[Tramo]:
    """Une tramos consecutivos del mismo modo/linea en uno solo."""
    fusionados: list[dict] = []
    for t in brutos:
        if (
            fusionados
            and fusionados[-1]["modo"] == t["modo"]
            and fusionados[-1]["linea"] == t["linea"]
        ):
            prev = fusionados[-1]
            prev["geom"].extend(t["geom"])
            prev["dist"] += t["dist"]
            prev["dur"] += t["dur"]
            prev["fare"] += t["fare"]
            prev["parada_hasta"] = t.get("parada_hasta")
        else:
            fusionados.append(dict(t))

    tramos: list[Tramo] = []
    for t in fusionados:
        geom = _geometria_unica(t["geom"])
        if len(geom) >= 1:
            desde = Coordenada(lat=geom[0][1], lon=geom[0][0])
            hasta = Coordenada(lat=geom[-1][1], lon=geom[-1][0])
        else:
            desde = hasta = Coordenada(lat=0, lon=0)
        geometria = (
            geo.linea_geojson(geom)
            if len(geom) >= 2
            else geo.punto_geojson(geom[0] if geom else (0.0, 0.0))
        )
        tramos.append(
            Tramo(
                modo=t["modo"],
                linea=t["linea"],
                desde=desde,
                hasta=hasta,
                distancia_m=round(t["dist"], 1),
                duracion_seg=round(t["dur"], 1),
                tarifa_cop=t["fare"],
                geometria=geometria,
                codigo=t.get("codigo"),
                parada_desde=t.get("parada_desde"),
                parada_hasta=t.get("parada_hasta"),
                espera_seg=round(t["espera"], 1) if t.get("espera") is not None else None,
            )
        )
    return tramos


def _modo_tramo(linea_tipo: str | None) -> str:
    if linea_tipo == "informal":
        return "informal"
    if linea_tipo == "cable":
        return "cable"
    if linea_tipo:
        return "formal"
    return "acceso"


def _a_resumen(aristas: list[_Arista], zonas: CatalogoZonas) -> RutaResumen:
    distancia = 0.0
    duracion = 0.0
    tarifa = 0.0
    boardings = 0
    brutos: list[dict] = []
    informales: list[str] = []
    formales: list[str] = []
    novedades: dict[str, NovedadResumen] = {}
    geometria: list[Punto] = []
    tarifa_por_linea: dict[str, float] = {}
    espera_pendiente: float | None = None

    for ar in aristas:
        meta = ar.meta
        tipo = meta["tipo"]
        duracion += ar.dt
        tarifa += ar.dfare
        for nov in meta.get("alertas") or []:
            novedades.setdefault(nov["id"], NovedadResumen(**nov))
        if tipo == "abordar":
            boardings += 1
            espera_pendiente = meta.get("espera_seg")
            if meta["linea"] is not None:
                tarifa_por_linea[meta["linea"]] = (
                    tarifa_por_linea.get(meta["linea"], 0.0) + ar.dfare
                )
            if meta.get("linea_tipo") == "informal":
                if meta["linea"] not in informales:
                    informales.append(meta["linea"])
            elif meta["linea"] not in formales:
                formales.append(meta["linea"])
            continue
        if tipo == "bajar":
            continue
        geom = meta.get("geometria") or []
        distancia += meta.get("distancia_m", 0.0)
        geometria.extend(geom)
        if tipo == "directo":
            modo = "directo"
        elif tipo == "informal":
            modo = _modo_tramo(meta.get("linea_tipo"))
        else:
            modo = "acceso"
        fare_tramo = 0.0
        espera = None
        if modo in {"cable", "formal", "informal"} and meta.get("linea"):
            fare_tramo = tarifa_por_linea.pop(meta["linea"], 0.0)
            espera, espera_pendiente = espera_pendiente, None
        brutos.append(
            {
                "modo": modo,
                "linea": meta.get("linea"),
                "geom": list(geom),
                "dist": meta.get("distancia_m", 0.0),
                "dur": ar.dt,
                "fare": fare_tramo,
                "codigo": meta.get("codigo"),
                "parada_desde": meta.get("parada_desde"),
                "parada_hasta": meta.get("parada_hasta"),
                "espera": espera,
            }
        )

    geometria = _geometria_unica(geometria)
    tramos = _fusionar_tramos(brutos)
    zonas_rec = zonas.zonas_del_recorrido(geometria)
    zonas_resumen = [ZonaResumen(**z.resumen()) for z in zonas_rec]
    return RutaResumen(
        distancia_m=round(distancia, 1),
        duracion_seg=round(duracion, 1),
        tarifa_total_cop=tarifa,
        transbordos=max(0, boardings - 1),
        geometria=geo.linea_geojson(geometria) if len(geometria) >= 2 else geo.punto_geojson(geometria[0] if geometria else (0.0, 0.0)),
        tramos=tramos,
        zonas=zonas_resumen,
        informales_usadas=informales,
        formales_usadas=formales,
        novedades=list(novedades.values()),
    )


def _firma(r: RutaResumen) -> str:
    coords = r.geometria.get("coordinates") or []
    puntos = [(round(c[0], 5), round(c[1], 5)) for c in coords]
    return str(puntos[:3] + puntos[-3:] + [len(puntos)])


def _costo_resumen(r: RutaResumen, pesos):
    abordajes = r.transbordos + 1 if r.tramos and any(t.linea for t in r.tramos) else 0
    return _costo(r.duracion_seg, r.tarifa_total_cop, abordajes, pesos)


def _contexto(
    zonas: CatalogoZonas | None,
    informales: CatalogoInformales | None,
    formales: CatalogoInformales | None,
    osrm: OSRMClient | None,
    alertas: AlmacenAlertas | None,
    hora: str | None,
    dia: str | None,
) -> Contexto:
    return Contexto(
        zonas=zonas or cargar_zonas(),
        informales=informales or cargar_informales(),
        formales=formales if formales is not None else cargar_formales(),
        osrm=osrm or cliente_osrm,
        alertas=alertas or almacen_alertas(),
        tarifas=cargar_tarifas(),
        hora=hora or hora_actual(),
        dia=dia or dia_letra(),
    )


def calcular_ruta(
    req: RutaRequest,
    zonas: CatalogoZonas | None = None,
    informales: CatalogoInformales | None = None,
    osrm: OSRMClient | None = None,
    formales: CatalogoInformales | None = None,
    alertas: AlmacenAlertas | None = None,
) -> tuple[RutaResumen, list[RutaResumen]]:
    ctx = _contexto(zonas, informales, formales, osrm, alertas, req.hora, req.dia)
    pesos = req.pesos

    o: Punto = (req.origen.lon, req.origen.lat)
    d: Punto = (req.destino.lon, req.destino.lat)
    if geo.haversine_m(o[1], o[0], d[1], d[0]) < 15:
        vacio = _a_resumen([], ctx.zonas)
        return vacio, []

    red, _ruta_directa = _construir_red(req, ctx)
    candidatas: list[RutaResumen] = []

    camino = _buscar(red, pesos)
    if camino is not None:
        candidatas.append(_a_resumen(camino, ctx.zonas))

    # Segunda opcion: sin la primera ruta de la mejor opcion (todas sus variantes, si es del SITP).
    if candidatas:
        usadas = candidatas[0].informales_usadas + candidatas[0].formales_usadas
        if usadas:
            primera = red.lineas.get(usadas[0])
            prohibida = {primera.grupo if primera else usadas[0]}
            red2, _ = _construir_red(req, ctx, prohibidas=prohibida)
            camino2 = _buscar(red2, pesos)
            if camino2 is not None:
                candidatas.append(_a_resumen(camino2, ctx.zonas))

    vistas: set[str] = set()
    unicas: list[RutaResumen] = []
    for r in candidatas:
        f = _firma(r)
        if f not in vistas:
            vistas.add(f)
            unicas.append(r)

    unicas.sort(key=lambda r: _costo_resumen(r, pesos))
    if not unicas:
        vacio = _a_resumen([], ctx.zonas)
        return vacio, []
    return unicas[0], unicas[1:3]
