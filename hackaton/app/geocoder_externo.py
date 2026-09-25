"""Geocoding externo por OpenStreetMap (servicio Photon). Sin API key."""
from __future__ import annotations

import threading
import time

import requests

from .config import settings
from .geocoder import Lugar

# Sesgo hacia Ciudad Bolivar / Bogota para desempatar resultados.
_BIAS_LAT = 4.56
_BIAS_LON = -74.14
# Bbox de Bogota (min_lon, min_lat, max_lon, max_lat) para descartar resultados lejanos.
_BBOX = (-74.30, 4.35, -73.90, 4.95)

_cache: dict[str, tuple[float, list[Lugar]]] = {}
_lock = threading.Lock()
_TTL = 86400.0


def _en_bbox(lat: float, lon: float) -> bool:
    return _BBOX[0] <= lon <= _BBOX[2] and _BBOX[1] <= lat <= _BBOX[3]


def buscar_externo(consulta: str, limite: int = 3) -> list[Lugar]:
    """Busca lugares/direcciones en OSM (Photon). Devuelve [] si falla."""
    q = (consulta or "").strip()
    if not q or not settings.geocoder_externo:
        return []

    clave = f"{q.lower()}|{limite}"
    with _lock:
        item = _cache.get(clave)
        if item and item[0] > time.time():
            return item[1]

    url = f"{settings.photon_url.rstrip('/')}/api/"
    params = {"q": q, "limit": limite, "lat": _BIAS_LAT, "lon": _BIAS_LON}
    try:
        resp = requests.get(
            url,
            params=params,
            timeout=settings.geocoder_timeout_s,
            headers={"User-Agent": "ConectaCB/2.0"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    lugares: list[Lugar] = []
    for f in data.get("features", []):
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            continue
        lon, lat = coords[0], coords[1]
        if not _en_bbox(lat, lon):
            continue
        props = f.get("properties") or {}
        nombre = props.get("name") or props.get("street") or q
        lugares.append(
            Lugar(
                nombre=str(nombre),
                tipo=str(props.get("osm_value") or "lugar"),
                lat=float(lat),
                lon=float(lon),
                alias=[],
            )
        )

    with _lock:
        _cache[clave] = (time.time() + _TTL, lugares)
    return lugares
