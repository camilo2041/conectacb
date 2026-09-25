"""Ruteo multimodal: red vial (OSRM) + lineas formales (cable/SITP) + informales.

Se construye un grafo pequeno cuyos nodos son el origen, el destino y las paradas
de las lineas candidatas (cercanas al origen/destino, mas las "puente" que conectan
por transbordo). Se corre Dijkstra con costo lexicografico
(tiempo, tarifa, transbordos) o ponderado si el request envia `pesos`.

Se integran ademas:
- horarios/frecuencia (espera segun la hora y servicio activo),
- tarifas integradas (TransMiCable/SITP con TransMilenio),
- novedades/alertas en vivo (retrasos que afectan el costo).
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass
from typing import Any

from . import geo
from .alertas import Alerta, AlmacenAlertas, almacen_alertas
from .config import settings
from .geo import Punto
from .informal import CatalogoInformales, LineaInformal, cargar_formales, cargar_informales
from .models import Coordenada, NovedadResumen, RutaRequest, RutaResumen, Tramo, ZonaResumen
from .osrm import OSRMClient, RutaOSRM, cliente_osrm
from .tarifas import cargar_tarifas
from .tiempo import dia_letra, hora_actual
from .zones import CatalogoZonas, cargar_zonas

# (nodo, linea_actual|None, integrado: 0/1)
Estado = tuple[str, str | None, int]


def _seg_caminata(dist_m: float, vel_kmh: float) -> float:
    return dist_m / (vel_kmh * 1000.0 / 3600.0)


def _cero(pesos):
    return (0.0, 0.0, 0) if pesos is None else 0.0


def _costo(dt: float, dfare: float, dtrans: float, pesos):
    if pesos is None:
        return (dt, dfare, int(dtrans))
    return pesos.tiempo * dt + pesos.tarifa * dfare + pesos.transbordos * dtrans


def _add(a, b):
    if isinstance(a, tuple):
        return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
    return a + b


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


def _arista_acceso(origen: Punto, destino: Punto, estado_destino: Estado, tipo: str = "acceso") -> _Arista:
    dist = geo.haversine_m(origen[1], origen[0], destino[1], destino[0])
    dt = _seg_caminata(dist, settings.velocidad_caminata_kmh)
    meta = {
        "tipo": tipo,
        "linea": None,
        "distancia_m": dist,
        "geometria": [origen, destino],
    }
    return _Arista(estado_destino, dt, 0.0, 0.0, meta)


def _lineas_conectan(a: LineaInformal, b: LineaInformal, radio_m: float) -> bool:
    """True si alguna parada de `a` esta a <= radio_m de alguna parada de `b`."""
    for pa in a.paradas:
        for pb in b.paradas:
            if geo.haversine_m(pa[1], pa[0], pb[1], pb[0]) <= radio_m:
                return True
    return False


def _construir_grafo(
    req: RutaRequest,
    ctx: Contexto,
    lineas_prohibidas: set[str] | None = None,
) -> tuple[dict[Estado, list[_Arista]], RutaOSRM]:
    prohibidas = lineas_prohibidas or set()
    o: Punto = (req.origen.lon, req.origen.lat)
    d: Punto = (req.destino.lon, req.destino.lat)
    radio = req.opciones.radio_acceso_m
    max_paradas = req.opciones.max_paradas_por_extremo
    radio_transbordo = settings.radio_transbordo_m
    tipos_integrados = set(ctx.tarifas.get("tipos_integrados") or [])

    adj: dict[Estado, list[_Arista]] = {}

    def agregar(estado: Estado, arista: _Arista) -> None:
        adj.setdefault(estado, []).append(arista)

    # Ruta directa O->D por la red vial (OSRM).
    if req.usar_directo:
        ruta_directa = ctx.osrm.ruta(o, d, req.perfil)
        alertas_directo = ctx.alertas.activas_para_geometria(ruta_directa.geometria)
        retraso = max((a.retraso_seg for a in alertas_directo), default=0.0)
        agregar(
            ("O", None, 0),
            _Arista(
                ("D", None, 0),
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
            ),
        )
    else:
        ruta_directa = OSRMClient._respaldo(o, d, req.perfil)

    if not req.usar_informales and not req.usar_formales:
        return adj, ruta_directa

    # Lineas candidatas: con alguna parada cerca del origen o del destino.
    lineas_cand: dict[str, LineaInformal] = {}

    def agregar_candidatas(catalogo: CatalogoInformales) -> None:
        for lin, _idx, _dist, _pto in catalogo.lineas_cercanas_a(o, radio)[:max_paradas]:
            if lin.id not in prohibidas:
                lineas_cand[lin.id] = lin
        for lin, _idx, _dist, _pto in catalogo.lineas_cercanas_a(d, radio)[:max_paradas]:
            if lin.id not in prohibidas:
                lineas_cand[lin.id] = lin

    if req.usar_informales:
        agregar_candidatas(ctx.informales)
    if req.usar_formales:
        agregar_candidatas(ctx.formales)

    # Expansion: incluir lineas "puente" que conectan por transbordo.
    todas: list[LineaInformal] = []
    if req.usar_informales:
        todas.extend(ctx.informales.lineas)
    if req.usar_formales:
        todas.extend(ctx.formales.lineas)
    for _ in range(max(0, req.opciones.max_transbordos)):
        nuevos: dict[str, LineaInformal] = {}
        for lin in todas:
            if lin.id in lineas_cand or lin.id in prohibidas:
                continue
            if any(
                _lineas_conectan(lin, cand, radio_transbordo)
                for cand in lineas_cand.values()
            ):
                nuevos[lin.id] = lin
        if not nuevos:
            break
        lineas_cand.update(nuevos)

    if not lineas_cand:
        return adj, ruta_directa

    # Nodos de parada.
    nodos: dict[str, tuple[LineaInformal, int, Punto]] = {}
    for lin in lineas_cand.values():
        for i, p in enumerate(lin.paradas):
            nodos[f"{lin.id}#{i}"] = (lin, i, p)

    for clave, (lin, idx, p) in nodos.items():
        d_o = geo.haversine_m(o[1], o[0], p[1], p[0])
        if d_o <= radio:
            agregar(("O", None, 0), _arista_acceso(o, p, (clave, None, 0)))
        d_d = geo.haversine_m(d[1], d[0], p[1], p[0])
        if d_d <= radio:
            for flag in (0, 1):
                agregar((clave, None, flag), _arista_acceso(p, d, ("D", None, flag)))
        # Transbordo a pie hacia otra parada cercana.
        for clave2, (_lin2, _i2, p2) in nodos.items():
            if clave2 == clave:
                continue
            if geo.haversine_m(p[1], p[0], p2[1], p2[0]) <= radio_transbordo:
                for flag in (0, 1):
                    agregar((clave, None, flag), _arista_acceso(p, p2, (clave2, None, flag), tipo="acceso"))

    # Abordar / recorrer / bajar por cada linea.
    for clave, (lin, idx, _p) in nodos.items():
        if lin.activo(ctx.hora, ctx.dia):
            integrado = lin.es_integrado(tipos_integrados)
            alertas_lin = ctx.alertas.activas_para_linea(lin)
            retraso = max((a.retraso_seg for a in alertas_lin), default=0.0)
            espera = lin.espera_seg(ctx.hora)
            novedades = [_novedad(a) for a in alertas_lin]
            for flag in (0, 1):
                fare = 0.0 if (integrado and flag == 1) else lin.tarifa
                nuevo_flag = 1 if integrado else 0
                agregar(
                    (clave, None, flag),
                    _Arista(
                        (clave, lin.id, nuevo_flag),
                        espera + retraso,
                        fare,
                        1.0,
                        {
                            "tipo": "abordar",
                            "linea": lin.id,
                            "linea_tipo": lin.tipo,
                            "tarifa_cop": fare,
                            "alertas": novedades,
                            "distancia_m": 0.0,
                            "geometria": [],
                        },
                    ),
                )
        # Bajar.
        for flag in (0, 1):
            agregar(
                (clave, lin.id, flag),
                _Arista((clave, None, flag), 0.0, 0.0, 0.0, {"tipo": "bajar", "linea": lin.id, "linea_tipo": lin.tipo, "distancia_m": 0.0, "geometria": []}),
            )
        # Recorrer.
        for clave2, (lin2, idx2, _p2) in nodos.items():
            if lin2.id != lin.id or idx2 == idx:
                continue
            geom, dist, dur = lin.tramo(idx, idx2)
            for flag in (0, 1):
                agregar(
                    (clave, lin.id, flag),
                    _Arista(
                        (clave2, lin.id, flag),
                        dur,
                        0.0,
                        0.0,
                        {
                            "tipo": "informal",
                            "linea": lin.id,
                            "linea_tipo": lin.tipo,
                            "desde_idx": idx,
                            "hasta_idx": idx2,
                            "distancia_m": dist,
                            "geometria": geom,
                        },
                    ),
                )
    return adj, ruta_directa


def _dijkstra(adj, inicio: Estado, objetivo: Estado, pesos) -> list[_Arista] | None:
    dist: dict[Estado, Any] = {inicio: _cero(pesos)}
    prev: dict[Estado, tuple[Estado, _Arista]] = {}
    contador = itertools.count()
    pq = [(_cero(pesos), next(contador), inicio)]
    nodo_objetivo = objetivo[0]
    while pq:
        costo, _, estado = heapq.heappop(pq)
        if estado[0] == nodo_objetivo:
            return _reconstruir(prev, estado)
        if costo > dist.get(estado, costo):
            continue
        for ar in adj.get(estado, []):
            nc = _add(costo, _costo(ar.dt, ar.dfare, ar.dtrans, pesos))
            actual = dist.get(ar.destino)
            if actual is None or nc < actual:
                dist[ar.destino] = nc
                prev[ar.destino] = (estado, ar)
                heapq.heappush(pq, (nc, next(contador), ar.destino))
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

    for ar in aristas:
        meta = ar.meta
        tipo = meta["tipo"]
        duracion += ar.dt
        tarifa += ar.dfare
        for nov in meta.get("alertas") or []:
            novedades.setdefault(nov["id"], NovedadResumen(**nov))
        if tipo == "abordar":
            boardings += 1
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
        if modo in {"cable", "formal", "informal"} and meta.get("linea"):
            fare_tramo = tarifa_por_linea.pop(meta["linea"], 0.0)
        brutos.append(
            {
                "modo": modo,
                "linea": meta.get("linea"),
                "geom": list(geom),
                "dist": meta.get("distancia_m", 0.0),
                "dur": ar.dt,
                "fare": fare_tramo,
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
    return _costo(r.duracion_seg, r.tarifa_total_cop, r.transbordos, pesos)


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

    adj, _ruta_directa = _construir_grafo(req, ctx)
    candidatas: list[RutaResumen] = []

    camino = _dijkstra(adj, ("O", None, 0), ("D", None, 0), pesos)
    if camino is not None:
        candidatas.append(_a_resumen(camino, ctx.zonas))

    # Segunda opcion: prohibir la primera linea (informal o formal) de la mejor ruta.
    if candidatas:
        usadas = candidatas[0].informales_usadas + candidatas[0].formales_usadas
        if usadas:
            prohibida = {usadas[0]}
            adj2, _ = _construir_grafo(req, ctx, lineas_prohibidas=prohibida)
            camino2 = _dijkstra(adj2, ("O", None, 0), ("D", None, 0), pesos)
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
