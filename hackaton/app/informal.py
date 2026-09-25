"""Carga de rutas informales (formato pluggable) y snapping de paradas."""
from __future__ import annotations

import glob
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import geo
from .config import settings
from .geo import Punto
from .tiempo import dentro_horario, espera_por_frecuencia

VELOCIDAD_DEFECTO_KMH = 22.0


@dataclass
class LineaInformal:
    id: str
    nombre: str
    modo: str
    tarifa: float
    tiempo_espera_seg: float
    frecuencia_min: float | None
    horario: dict[str, Any]
    velocidad_kmh: float
    geometria: list[Punto]
    paradas: list[Punto] = field(default_factory=list)
    indices_paradas: list[int] = field(default_factory=list)
    propiedades: dict[str, Any] = field(default_factory=dict)
    tipo: str = "informal"

    def _dur_seg(self, distancia_m: float) -> float:
        vel = self.velocidad_kmh or VELOCIDAD_DEFECTO_KMH
        return distancia_m / (vel * 1000.0 / 3600.0)

    def espera_seg(self, hora: str | None = None) -> float:
        """Espera esperada: media cabeza de frecuencia, o el valor fijo."""
        return espera_por_frecuencia(self.frecuencia_min, self.tiempo_espera_seg)

    def activo(self, hora: str | None = None, dia: str | None = None) -> bool:
        return dentro_horario(self.horario, hora, dia)

    def es_integrado(self, tipos_integrados: set[str] | None = None) -> bool:
        if self.propiedades.get("integrado") is True:
            return True
        if tipos_integrados is None:
            from .tarifas import cargar_tarifas

            tipos_integrados = set(cargar_tarifas().get("tipos_integrados") or [])
        return self.tipo in tipos_integrados

    def parada_cercana(self, p: Punto) -> tuple[int, float, Punto]:
        """Devuelve (indice_parada, distancia_m, punto_parada)."""
        mejor_idx = 0
        mejor_d = float("inf")
        mejor_p = self.paradas[0] if self.paradas else p
        for i, parada in enumerate(self.paradas):
            d = geo.haversine_m(p[1], p[0], parada[1], parada[0])
            if d < mejor_d:
                mejor_d, mejor_idx, mejor_p = d, i, parada
        return mejor_idx, mejor_d, mejor_p

    def tramo(self, i: int, j: int) -> tuple[list[Punto], float, float]:
        """Geometria, distancia y duracion entre dos paradas, en el sentido del viaje (de i hacia j)."""
        a, b = (i, j) if i <= j else (j, i)
        ga = self.indices_paradas[a] if self.indices_paradas else a
        gb = self.indices_paradas[b] if self.indices_paradas else b
        geom = self.geometria[ga : gb + 1]
        if i > j:
            # Se recorre la linea al reves de como esta dibujada.
            geom = geom[::-1]
        dist = geo.longitud_linea_m(geom)
        return geom, dist, self._dur_seg(dist)

    def resumen(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "modo": self.modo,
            "tipo": self.tipo,
            "tarifa": self.tarifa,
            "integrado": self.es_integrado(),
            "espera_seg": round(self.espera_seg(), 1),
            "frecuencia_min": self.frecuencia_min,
            "velocidad_kmh": self.velocidad_kmh,
            "horario": self.horario,
            "num_paradas": len(self.paradas),
            "geometria": geo.linea_geojson(self.geometria),
        }


def _paradas_desde(props: dict[str, Any], geometria: list[Punto]) -> tuple[list[Punto], list[int]]:
    """Devuelve (paradas, indices_geometria). Sin `paradas` explicitas usa todos los vertices."""
    explicitas = props.get("paradas")
    if not explicitas:
        return list(geometria), list(range(len(geometria)))
    # Ordena las paradas explicitas por su vertice mas cercano en la linea. Se usa el vertice
    # mas cercano (no el inicio del segmento mas cercano): las estaciones del cable son vertices
    # y, con el inicio del segmento, cada una quedaba asignada a la pilona anterior.
    pares: list[tuple[int, Punto]] = []
    for par in explicitas:
        p = (par[0], par[1])
        idx = min(range(len(geometria)), key=lambda k: geo.haversine_m(p[1], p[0], geometria[k][1], geometria[k][0]))
        pares.append((idx, p))
    pares.sort(key=lambda t: t[0])
    return [p for _, p in pares], [idx for idx, _ in pares]


class CatalogoInformales:
    def __init__(self, lineas: list[LineaInformal], geojson_crudo: dict):
        self.lineas = lineas
        self.geojson_crudo = geojson_crudo

    def lineas_cercanas_a(self, p: Punto, radio_m: float) -> list[tuple[LineaInformal, int, float, Punto]]:
        resultado: list[tuple[float, LineaInformal, int, float, Punto]] = []
        for linea in self.lineas:
            idx, d, punto = linea.parada_cercana(p)
            if d <= radio_m:
                resultado.append((d, linea, idx, d, punto))
        resultado.sort(key=lambda t: t[0])
        return [(lin, idx, d, punto) for _, lin, idx, d, punto in resultado]

    def por_id(self, id_linea: str) -> LineaInformal | None:
        for lin in self.lineas:
            if lin.id == id_linea:
                return lin
        return None


def _cargar_varios(paths: list[Path], tipo_defecto: str = "informal") -> CatalogoInformales:
    features: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as fh:
            crudo = json.load(fh)
        features.extend(crudo.get("features", []))
    crudo_merged: dict[str, Any] = {"type": "FeatureCollection", "features": features}

    lineas: list[LineaInformal] = []
    for i, feat in enumerate(features):
        geom = feat.get("geometry") or {}
        if geom.get("type") != "LineString":
            continue
        geometria = [(c[0], c[1]) for c in geom.get("coordinates", [])]
        if len(geometria) < 2:
            continue
        props = feat.get("properties", {}) or {}
        paradas, indices_paradas = _paradas_desde(props, geometria)
        lineas.append(
            LineaInformal(
                id=str(props.get("id") or f"INF-{i + 1:03d}"),
                nombre=str(props.get("nombre") or props.get("id") or f"Ruta {i + 1}"),
                modo=str(props.get("modo") or "informal"),
                tarifa=float(props.get("tarifa") or 0),
                tiempo_espera_seg=float(props.get("tiempo_espera_seg") or 0),
                frecuencia_min=(
                    float(props["frecuencia_min"])
                    if props.get("frecuencia_min") is not None
                    else None
                ),
                horario=props.get("horario") or {},
                velocidad_kmh=float(props.get("velocidad_kmh") or VELOCIDAD_DEFECTO_KMH),
                geometria=geometria,
                paradas=paradas,
                indices_paradas=indices_paradas,
                propiedades=props,
                tipo=str(props.get("tipo") or tipo_defecto),
            )
        )
    return CatalogoInformales(lineas, crudo_merged)


@lru_cache(maxsize=1)
def cargar_informales(path: str | None = None) -> CatalogoInformales:
    if path:
        return _cargar_varios([Path(path)], tipo_defecto="informal")
    paths = sorted(Path(p) for p in glob.glob(settings.informales_glob))
    if not paths:
        paths = [settings.informales_path]
    return _cargar_varios(paths, tipo_defecto="informal")


@lru_cache(maxsize=1)
def cargar_formales(path: str | None = None) -> CatalogoInformales:
    """Rutas formales (p. ej. TransMiCable)."""
    if path:
        return _cargar_varios([Path(path)], tipo_defecto="formal")
    paths = sorted(Path(p) for p in glob.glob(settings.formales_glob))
    return _cargar_varios(paths, tipo_defecto="formal")
