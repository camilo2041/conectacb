"""Carga y consulta de las zonas SITP (poligonos)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from . import geo
from .config import settings


@dataclass
class Zona:
    propiedades: dict[str, Any]
    multipoligono: list  # [[[ (lon,lat), ... ], huecos...], ...]
    bbox: tuple[float, float, float, float]

    @property
    def nombre(self) -> str | None:
        return self.propiedades.get("nombre")

    def resumen(self) -> dict[str, Any]:
        return {
            "nombre": self.propiedades.get("nombre"),
            "zona": self.propiedades.get("zona"),
            "color": self.propiedades.get("color"),
            "letra": self.propiedades.get("letra"),
            "rango": self.propiedades.get("rango"),
        }


def _normalizar_geometria(geom: dict) -> list:
    """Convierte Polygon o MultiPolygon a lista de poligonos."""
    tipo = geom.get("type")
    coords = geom.get("coordinates") or []
    if tipo == "Polygon":
        return [coords]
    if tipo == "MultiPolygon":
        return coords
    return []


class CatalogoZonas:
    def __init__(self, zonas: list[Zona], geojson_crudo: dict):
        self.zonas = zonas
        self.geojson_crudo = geojson_crudo

    def zona_en_punto(self, lon: float, lat: float) -> Zona | None:
        for z in self.zonas:
            if not geo._en_bbox(lon, lat, z.bbox):
                continue
            if geo.punto_en_multipoligono(lon, lat, z.multipoligono):
                return z
        return None

    def zonas_cercanas(self, lon: float, lat: float, radio_m: float) -> list[Zona]:
        resultado: list[tuple[float, Zona]] = []
        for z in self.zonas:
            d = geo.distancia_punto_a_multipoligono_m((lon, lat), z.multipoligono)
            if d <= radio_m:
                resultado.append((d, z))
        resultado.sort(key=lambda t: t[0])
        return [z for _, z in resultado]

    def zonas_del_recorrido(self, linea: Sequence[geo.Punto]) -> list[Zona]:
        """Zonas cruzadas por una linea, en orden de aparicion (sin repetir)."""
        if not linea:
            return []
        muestras: list[geo.Punto] = list(linea)
        for i in range(len(linea) - 1):
            a, b = linea[i], linea[i + 1]
            muestras.append(geo.interpolar(a, b, 0.5))
        vistas: list[str] = []
        orden: list[Zona] = []
        for lon, lat in muestras:
            z = self.zona_en_punto(lon, lat)
            if z is None:
                continue
            clave = z.propiedades.get("globalid") or z.nombre or str(id(z))
            if clave not in vistas:
                vistas.append(clave)
                orden.append(z)
        return orden


def _cargar(path: Path) -> CatalogoZonas:
    with open(path, encoding="utf-8") as fh:
        crudo = json.load(fh)
    zonas: list[Zona] = []
    for feat in crudo.get("features", []):
        geom = feat.get("geometry") or {}
        multipoligono = _normalizar_geometria(geom)
        anillos: list[geo.Punto] = []
        for poly in multipoligono:
            for anillo in poly:
                for par in anillo:
                    anillos.append((par[0], par[1]))
        zonas.append(
            Zona(
                propiedades=feat.get("properties", {}),
                multipoligono=multipoligono,
                bbox=geo.bbox(anillos) if anillos else (0, 0, 0, 0),
            )
        )
    return CatalogoZonas(zonas, crudo)


@lru_cache(maxsize=1)
def cargar_zonas(path: str | None = None) -> CatalogoZonas:
    return _cargar(Path(path) if path else settings.zonas_path)
