"""Geocoding externo por OpenStreetMap (servicio Photon). Sin API key.

Busca primero dentro de Ciudad Bolivar: muchos barrios de la localidad comparten nombre con
barrios de Bosa, Kennedy o el norte (El Recreo, San Bernardino, Jerusalen, La Estrella...) y sin
ese filtro Photon devuelve el de otra localidad. Solo si nada coincide en Ciudad Bolivar se
busca en el resto de Bogota.
"""
from __future__ import annotations

import threading
import time

import requests

from .config import settings
from .geocoder import Lugar, normalizar

# Sesgo hacia Ciudad Bolivar para desempatar resultados.
_BIAS_LAT = 4.56
_BIAS_LON = -74.15
# Recuadros (min_lon, min_lat, max_lon, max_lat).
_BBOX_CB = (-74.21, 4.44, -74.12, 4.60)  # Ciudad Bolivar, urbana y rural
_BBOX_BOGOTA = (-74.30, 4.35, -73.90, 4.95)

# Palabras que no distinguen un lugar de otro.
_VACIAS = {"de", "del", "la", "las", "el", "los", "y", "barrio", "sector", "vereda", "estacion"}

# Resultados de Photon que son lugares habitados: se prefieren sobre colegios, paraderos, etc.
_LUGARES_OSM = {"neighbourhood", "quarter", "suburb", "village", "hamlet", "locality", "isolated_dwelling"}
# Comercios: comparten nombre con barrios ("Hostal Villa Gloria", "Frutas de mi Tierra Linda")
# y no son lo que la gente pide como origen o destino.
_COMERCIOS_KEY = {"shop", "tourism", "craft", "office"}
_COMERCIOS_VALUE = {"restaurant", "cafe", "fast_food", "bar", "pub", "pharmacy", "bank", "pawnbroker"}

_cache: dict[str, tuple[float, list[Lugar]]] = {}
_lock = threading.Lock()
_TTL = 86400.0


def _en_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def _coincide(consulta: str, nombre: str) -> bool:
    """True si todas las palabras significativas de la consulta estan en el nombre.

    Photon tolera errores de tipeo y devuelve lugares con nombres solo parecidos
    ("La Cordillera" -> "Drogueria La Gran Cordiliena"); esos se descartan.
    """
    palabras = [p for p in normalizar(consulta).split() if p not in _VACIAS]
    nombre_n = normalizar(nombre)
    return all(p in nombre_n for p in palabras)


def _consultar(q: str, limite: int, bbox: tuple[float, float, float, float]) -> list[Lugar] | None:
    """Consulta Photon dentro de `bbox`. Devuelve None si el servicio falla."""
    params = {
        "q": q,
        "limit": max(limite, 10),  # se piden mas porque luego se filtran
        "lat": _BIAS_LAT,
        "lon": _BIAS_LON,
        "bbox": ",".join(str(v) for v in bbox),
    }
    # El servidor publico de Photon limita las rafagas de consultas: un reintento corto lo resuelve.
    for intento in range(2):
        try:
            resp = requests.get(
                f"{settings.photon_url.rstrip('/')}/api/",
                params=params,
                timeout=settings.geocoder_timeout_s,
                headers={"User-Agent": "ConectaCB/2.0"},
            )
            resp.raise_for_status()
            data = resp.json()
            break
        except (requests.RequestException, ValueError):
            if intento == 1:
                return None
            time.sleep(1.0)

    candidatos: list[tuple[int, Lugar]] = []
    for orden, f in enumerate(data.get("features", [])):
        coords = (f.get("geometry") or {}).get("coordinates")
        if not coords:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        props = f.get("properties") or {}
        nombre = props.get("name") or props.get("street")
        if not nombre or not _en_bbox(lat, lon, bbox) or not _coincide(q, nombre):
            continue
        tipo = str(props.get("osm_value") or "lugar")
        if props.get("osm_key") in _COMERCIOS_KEY or tipo in _COMERCIOS_VALUE:
            continue
        # Barrios y veredas primero; dentro de cada grupo, el orden de Photon.
        prioridad = orden if tipo in _LUGARES_OSM else orden + 1000
        candidatos.append((prioridad, Lugar(nombre=str(nombre), tipo=tipo, lat=lat, lon=lon, alias=[])))
    candidatos.sort(key=lambda c: c[0])
    return [lugar for _, lugar in candidatos[:limite]]


def buscar_externo(consulta: str, limite: int = 3) -> list[Lugar]:
    """Busca lugares/direcciones en OSM (Photon), primero en Ciudad Bolivar. Devuelve [] si falla."""
    q = (consulta or "").strip()
    if not q or not settings.geocoder_externo:
        return []

    clave = f"{q.lower()}|{limite}"
    with _lock:
        item = _cache.get(clave)
        if item and item[0] > time.time():
            return item[1]

    lugares = _consultar(q, limite, _BBOX_CB)
    if lugares == []:
        lugares = _consultar(q, limite, _BBOX_BOGOTA)
    if lugares is None:
        return []  # servicio caido: no se guarda en cache

    with _lock:
        _cache[clave] = (time.time() + _TTL, lugares)
    return lugares
