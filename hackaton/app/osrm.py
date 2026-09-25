"""Cliente HTTP para el servidor publico de OSRM."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import requests

from .config import settings
from .geo import Punto, haversine_m

_PERFILES_VALIDOS = {"driving", "walking", "cycling", "foot", "bike"}


class OSRMError(RuntimeError):
    pass


@dataclass
class RutaOSRM:
    distancia_m: float
    duracion_seg: float
    geometria: list[Punto]
    perfil: str
    aprox: bool = False  # True si se uso la linea recta de respaldo


class _CacheTTL:
    def __init__(self, ttl_s: float, max_items: int):
        self.ttl_s = ttl_s
        self.max_items = max_items
        self._data: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expira, valor = item
            if expira < time.time():
                self._data.pop(key, None)
                return None
            return valor

    def set(self, key: str, valor) -> None:
        with self._lock:
            if len(self._data) >= self.max_items:
                # Descarta el mas antiguo.
                mas_viejo = min(self._data.items(), key=lambda kv: kv[1][0])[0]
                self._data.pop(mas_viejo, None)
            self._data[key] = (time.time() + self.ttl_s, valor)


class OSRMClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_s: float | None = None,
        ttl_s: float | None = None,
        max_items: int | None = None,
    ):
        self.base_url = (base_url or settings.osrm_base_url).rstrip("/")
        self.timeout_s = timeout_s if timeout_s is not None else settings.osrm_timeout_s
        self.cache = _CacheTTL(
            ttl_s if ttl_s is not None else settings.osrm_cache_ttl_s,
            max_items if max_items is not None else settings.osrm_cache_max,
        )
        self.session = requests.Session()

    def _clave(self, a: Punto, b: Punto, perfil: str) -> str:
        return (
            f"{perfil}|{a[0]:.5f},{a[1]:.5f}|{b[0]:.5f},{b[1]:.5f}"
        )

    def ruta(
        self, a: Punto, b: Punto, perfil: str = "driving", permitir_respaldo: bool = True
    ) -> RutaOSRM:
        perfil_norm = "foot" if perfil == "walking" else ("bike" if perfil == "cycling" else perfil)
        if perfil_norm not in _PERFILES_VALIDOS:
            perfil_norm = "driving"
        clave = self._clave(a, b, perfil_norm)
        cacheado = self.cache.get(clave)
        if isinstance(cacheado, RutaOSRM):
            return cacheado

        url = (
            f"{self.base_url}/route/v1/{perfil_norm}/"
            f"{a[0]:.6f},{a[1]:.6f};{b[0]:.6f},{b[1]:.6f}"
        )
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout_s)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                raise OSRMError(f"OSRM sin ruta: {data.get('code')}")
            r = data["routes"][0]
            geom = [(c[0], c[1]) for c in r["geometry"]["coordinates"]]
            ruta = RutaOSRM(
                distancia_m=float(r["distance"]),
                duracion_seg=float(r["duration"]),
                geometria=geom,
                perfil=perfil_norm,
            )
            self.cache.set(clave, ruta)
            return ruta
        except (requests.RequestException, OSRMError, KeyError, ValueError) as exc:
            if not permitir_respaldo:
                raise OSRMError(str(exc)) from exc
            return self._respaldo(a, b, perfil_norm)

    @staticmethod
    def _respaldo(a: Punto, b: Punto, perfil: str) -> RutaOSRM:
        geom = [a, b]
        dist = haversine_m(a[1], a[0], b[1], b[0])
        vel = {"foot": 4.8, "bike": 15.0, "walking": 4.8, "cycling": 15.0}.get(perfil, 30.0)
        dur = dist / (vel * 1000 / 3600) if vel else dist
        return RutaOSRM(
            distancia_m=dist, duracion_seg=dur, geometria=geom, perfil=perfil, aprox=True
        )


def longitud(a: Punto, b: Punto) -> float:
    return haversine_m(a[1], a[0], b[1], b[0])


cliente_osrm = OSRMClient()
