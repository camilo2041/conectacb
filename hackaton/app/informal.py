"""Carga de rutas (informales, TransMiCable y SITP desde GTFS) y snapping de paradas."""
from __future__ import annotations

import bisect
import glob
import json
import statistics
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

from . import geo
from .config import settings
from .geo import Punto
from .tiempo import DIAS, dentro_horario, espera_por_frecuencia, parse_hora

VELOCIDAD_DEFECTO_KMH = 22.0

# Recuadro de Ciudad Bolivar (min_lon, min_lat, max_lon, max_lat), el mismo del importador GTFS.
BBOX_CIUDAD_BOLIVAR = (-74.21, 4.44, -74.12, 4.60)

# Tipo de dia de las salidas del GTFS segun la letra del dia.
_TIPO_DIA = {"L": "habil", "M": "habil", "X": "habil", "J": "habil", "V": "habil", "S": "sabado", "D": "domingo"}
# Sin una salida en esta ventana, la ruta se considera sin servicio a esa hora.
ESPERA_MAXIMA_MIN = 60


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
    # Rutas del GTFS: van en un solo sentido, con tiempos y salidas programadas reales.
    sentido_unico: bool = False
    tiempos_seg: list[float] | None = None
    salidas_min: dict[str, list[int]] | None = None
    paradas_nombre: list[str] | None = None
    paradas_id: list[str] | None = None

    def clave_parada(self, idx: int) -> str:
        """Identificador del paradero fisico: lo comparten las rutas del SITP que paran en el."""
        if self.paradas_id:
            return f"P:{self.paradas_id[idx]}"
        return f"{self.id}#{idx}"

    @property
    def codigo(self) -> str | None:
        return self.propiedades.get("codigo")

    @property
    def grupo(self) -> str:
        """Lineas que el usuario ve como la misma ruta (variantes de un mismo codigo del SITP)."""
        return f"{self.modo}:{self.codigo}" if self.codigo else self.id

    @cached_property
    def bbox(self) -> tuple[float, float, float, float]:
        return geo.bbox(self.geometria)

    @cached_property
    def en_ciudad_bolivar(self) -> bool:
        x0, y0, x1, y1 = BBOX_CIUDAD_BOLIVAR
        return any(x0 <= lon <= x1 and y0 <= lat <= y1 for lon, lat in self.paradas or self.geometria)

    def _dur_seg(self, distancia_m: float) -> float:
        vel = self.velocidad_kmh or VELOCIDAD_DEFECTO_KMH
        return distancia_m / (vel * 1000.0 / 3600.0)

    def _salida_siguiente(self, hora: str | None, dia: str | None, idx: int) -> float | None:
        """Minutos hasta que pasa el siguiente bus por la parada `idx`, segun las salidas del GTFS."""
        ahora = parse_hora(hora)
        salidas = (self.salidas_min or {}).get(_TIPO_DIA.get((dia or "L").upper(), "habil")) or []
        if ahora is None or not salidas:
            return None
        desfase = (self.tiempos_seg[idx] / 60.0) if self.tiempos_seg else 0.0
        # Salida desde la cabecera para pasar por la parada a partir de `ahora`.
        buscada = ahora - desfase
        k = bisect.bisect_left(salidas, buscada)
        if k == len(salidas):
            return None
        return salidas[k] - buscada

    def espera_seg(self, hora: str | None = None, dia: str | None = None, idx: int = 0) -> float:
        """Espera esperada: la siguiente salida programada, la media frecuencia, o el valor fijo."""
        if self.salidas_min:
            espera = self._salida_siguiente(hora, dia, idx)
            if espera is not None:
                return espera * 60.0
        return espera_por_frecuencia(self.frecuencia_min, self.tiempo_espera_seg)

    def activo(self, hora: str | None = None, dia: str | None = None, idx: int = 0) -> bool:
        if self.salidas_min:
            if hora is None:
                return True
            espera = self._salida_siguiente(hora, dia, idx)
            return espera is not None and espera <= ESPERA_MAXIMA_MIN
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
        geom = list(self.geometria[ga : gb + 1])
        if i > j:
            # Se recorre la linea al reves de como esta dibujada.
            geom = geom[::-1]
        if len(geom) >= 2 and self.paradas:
            # Empieza y termina en el paradero exacto (el vertice del trazado puede estar a unos metros).
            geom[0], geom[-1] = self.paradas[i], self.paradas[j]
        dist = geo.longitud_linea_m(geom)
        if self.tiempos_seg:
            return geom, dist, abs(self.tiempos_seg[j] - self.tiempos_seg[i])
        return geom, dist, self._dur_seg(dist)

    def nombre_parada(self, idx: int) -> str | None:
        return self.paradas_nombre[idx] if self.paradas_nombre else None

    def resumen(self, geometria: bool = True) -> dict[str, Any]:
        datos = {
            "id": self.id,
            "nombre": self.nombre,
            "codigo": self.codigo,
            "destino": self.propiedades.get("destino"),
            "modo": self.modo,
            "tipo": self.tipo,
            "tarifa": self.tarifa,
            "integrado": self.es_integrado(),
            "espera_seg": round(self.espera_seg(), 1),
            "frecuencia_min": self.frecuencia_min,
            "velocidad_kmh": self.velocidad_kmh,
            "horario": self.horario,
            "num_paradas": len(self.paradas),
            "en_ciudad_bolivar": self.en_ciudad_bolivar,
            "fuente": self.propiedades.get("fuente"),
        }
        if geometria:
            # Paraderos y trazado solo en la version completa: con el SITP son varios MB.
            if self.paradas_nombre:
                datos["paradas"] = [
                    {"nombre": n, "lat": p[1], "lon": p[0]} for n, p in zip(self.paradas_nombre, self.paradas)
                ]
            datos["geometria"] = geo.linea_geojson(self.geometria)
        return datos


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


def _horario_de_salidas(salidas: dict[str, list[int]]) -> tuple[dict[str, Any], float | None]:
    """Horario (primera/ultima salida, dias) y frecuencia tipica de dia habil, desde las salidas del GTFS."""
    todas = sorted(m for lista in salidas.values() for m in lista)
    dias = [d for d in DIAS if salidas.get(_TIPO_DIA[d])]
    horario: dict[str, Any] = {}
    if todas:
        fmt = lambda m: f"{(m // 60) % 24:02d}:{m % 60:02d}"  # noqa: E731
        horario = {"ini": fmt(todas[0]), "fin": fmt(todas[-1]), "dias": dias}
    habil = sorted(salidas.get("habil") or [])
    # Frecuencia: mediana entre salidas de 6:00 a 20:00 en dia habil.
    diurnas = [m for m in habil if 360 <= m <= 1200]
    intervalos = [b - a for a, b in zip(diurnas, diurnas[1:]) if b > a]
    frecuencia = float(statistics.median(intervalos)) if intervalos else None
    return horario, frecuencia


class CatalogoInformales:
    def __init__(self, lineas: list[LineaInformal], geojson_crudo: dict):
        self.lineas = lineas
        self.geojson_crudo = geojson_crudo
        self._por_id = {lin.id: lin for lin in lineas}

    def lineas_cercanas_a(self, p: Punto, radio_m: float) -> list[tuple[LineaInformal, int, float, Punto]]:
        resultado: list[tuple[float, LineaInformal, int, float, Punto]] = []
        for linea in self.lineas:
            idx, d, punto = linea.parada_cercana(p)
            if d <= radio_m:
                resultado.append((d, linea, idx, d, punto))
        resultado.sort(key=lambda t: t[0])
        return [(lin, idx, d, punto) for _, lin, idx, d, punto in resultado]

    def por_id(self, id_linea: str) -> LineaInformal | None:
        return self._por_id.get(id_linea)


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
        if props.get("indices_paradas"):
            # GTFS: el importador ya ubico cada paradero en el trazado, en orden de recorrido.
            paradas = [(p[0], p[1]) for p in props["paradas"]]
            indices_paradas = [int(k) for k in props["indices_paradas"]]
        else:
            paradas, indices_paradas = _paradas_desde(props, geometria)
        salidas = props.get("salidas_min")
        horario = props.get("horario") or {}
        frecuencia = float(props["frecuencia_min"]) if props.get("frecuencia_min") is not None else None
        if salidas:
            horario, frecuencia = _horario_de_salidas(salidas)
        lineas.append(
            LineaInformal(
                id=str(props.get("id") or f"INF-{i + 1:03d}"),
                nombre=str(props.get("nombre") or props.get("id") or f"Ruta {i + 1}"),
                modo=str(props.get("modo") or "informal"),
                tarifa=float(props.get("tarifa") or 0),
                tiempo_espera_seg=float(props.get("tiempo_espera_seg") or 0),
                frecuencia_min=frecuencia,
                horario=horario,
                velocidad_kmh=float(props.get("velocidad_kmh") or VELOCIDAD_DEFECTO_KMH),
                geometria=geometria,
                paradas=paradas,
                indices_paradas=indices_paradas,
                # Sin los datos pesados del GTFS: ya estan en los campos propios.
                propiedades={k: v for k, v in props.items() if k not in _PROPS_GTFS},
                tipo=str(props.get("tipo") or tipo_defecto),
                sentido_unico=bool(props.get("sentido_unico")),
                tiempos_seg=[float(t) for t in props["tiempos_seg"]] if props.get("tiempos_seg") else None,
                salidas_min=salidas,
                paradas_nombre=props.get("paradas_nombre"),
                paradas_id=[str(s) for s in props["paradas_id"]] if props.get("paradas_id") else None,
            )
        )
    return CatalogoInformales(lineas, crudo_merged)


_PROPS_GTFS = {"paradas", "paradas_id", "paradas_nombre", "indices_paradas", "tiempos_seg", "salidas_min"}


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
