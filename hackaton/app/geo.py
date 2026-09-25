"""Utilidades geometricas en Python puro (WGS84, orden lon/lat)."""
from __future__ import annotations

import math
from typing import Iterable, Sequence

R_TIERRA_M = 6371000.0

Punto = tuple[float, float]  # (lon, lat)


def _rad(deg: float) -> float:
    return deg * math.pi / 180.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia ortodromica en metros."""
    dlat = _rad(lat2 - lat1)
    dlon = _rad(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(_rad(lat1)) * math.cos(_rad(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * R_TIERRA_M * math.asin(min(1.0, math.sqrt(a)))


def bbox(coords: Iterable[Punto]) -> tuple[float, float, float, float]:
    """Devuelve (min_lon, min_lat, max_lon, max_lat)."""
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_expandida(
    b: tuple[float, float, float, float], metros: float
) -> tuple[float, float, float, float]:
    """Expande un bbox una cantidad aproximada de metros."""
    min_lon, min_lat, max_lon, max_lat = b
    dlat = metros / R_TIERRA_M * 180.0 / math.pi
    lat_media = (min_lat + max_lat) / 2.0
    dlon = dlat / max(0.05, math.cos(_rad(lat_media)))
    return min_lon - dlon, min_lat - dlat, max_lon + dlon, max_lat + dlat


def _en_bbox(lon: float, lat: float, b: tuple[float, float, float, float]) -> bool:
    return b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


def _punto_en_anillo(lon: float, lat: float, anillo: Sequence[Punto]) -> bool:
    """Ray casting clasico sobre un anillo cerrado o abierto."""
    dentro = False
    n = len(anillo)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        ):
            dentro = not dentro
        j = i
    return dentro


def punto_en_poligono(lon: float, lat: float, poligono: Sequence[Sequence[Punto]]) -> bool:
    """poligono = [anillo_exterior, huecos...]. True si el punto esta dentro."""
    if not poligono:
        return False
    if not _punto_en_anillo(lon, lat, poligono[0]):
        return False
    for hueco in poligono[1:]:
        if _punto_en_anillo(lon, lat, hueco):
            return False
    return True


def punto_en_multipoligono(
    lon: float, lat: float, multipoligono: Sequence[Sequence[Sequence[Punto]]]
) -> bool:
    return any(punto_en_poligono(lon, lat, poly) for poly in multipoligono)


def _proyectar_local(p: Punto, lat_ref: float) -> tuple[float, float]:
    x = _rad(p[0]) * math.cos(_rad(lat_ref)) * R_TIERRA_M
    y = _rad(p[1]) * R_TIERRA_M
    return x, y


def distancia_punto_a_segmento_m(p: Punto, a: Punto, b: Punto) -> tuple[float, float]:
    """Distancia minima del punto p al segmento a-b y el parametro t en [0,1]."""
    lat_ref = p[1]
    px, py = _proyectar_local(p, lat_ref)
    ax, ay = _proyectar_local(a, lat_ref)
    bx, by = _proyectar_local(b, lat_ref)
    dx, dy = bx - ax, by - ay
    largo2 = dx * dx + dy * dy
    if largo2 <= 1e-9:
        return math.hypot(px - ax, py - ay), 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / largo2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy), t


def distancia_punto_a_linea_m(p: Punto, linea: Sequence[Punto]) -> float:
    if not linea:
        return float("inf")
    if len(linea) == 1:
        return haversine_m(p[1], p[0], linea[0][1], linea[0][0])
    mejor = float("inf")
    for i in range(len(linea) - 1):
        d, _ = distancia_punto_a_segmento_m(p, linea[i], linea[i + 1])
        if d < mejor:
            mejor = d
    return mejor


def distancia_punto_a_multipoligono_m(p: Punto, multipoligono: Sequence) -> float:
    """Distancia minima de un punto al borde de un MultiPolygon."""
    mejor = float("inf")
    for poly in multipoligono:
        for anillo in poly:
            if len(anillo) < 2:
                continue
            d = distancia_punto_a_linea_m(p, [(c[0], c[1]) for c in anillo])
            if d < mejor:
                mejor = d
    return mejor


def longitud_linea_m(linea: Sequence[Punto]) -> float:
    total = 0.0
    for i in range(len(linea) - 1):
        total += haversine_m(linea[i][1], linea[i][0], linea[i + 1][1], linea[i + 1][0])
    return total


def punto_mas_cercano_en_linea(p: Punto, linea: Sequence[Punto]) -> tuple[float, Punto, int]:
    """Devuelve (distancia_m, punto_proyectado, indice_del_vertice_anterior)."""
    if not linea:
        return float("inf"), p, 0
    if len(linea) == 1:
        return haversine_m(p[1], p[0], linea[0][1], linea[0][0]), linea[0], 0
    mejor_d = float("inf")
    mejor_punto = linea[0]
    mejor_idx = 0
    for i in range(len(linea) - 1):
        a, b = linea[i], linea[i + 1]
        d, t = distancia_punto_a_segmento_m(p, a, b)
        if d < mejor_d:
            mejor_d = d
            mejor_punto = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            mejor_idx = i
    return mejor_d, mejor_punto, mejor_idx


def interpolar(a: Punto, b: Punto, t: float) -> Punto:
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def linea_geojson(linea: Sequence[Punto]) -> dict:
    return {"type": "LineString", "coordinates": [[p[0], p[1]] for p in linea]}


def punto_geojson(p: Punto) -> dict:
    return {"type": "Point", "coordinates": [p[0], p[1]]}
