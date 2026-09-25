"""Novedades/alertas en vivo: modelo, almacen CRUD y afectacion a rutas."""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from . import geo
from .config import settings
from .geo import Punto

TIPOS = {"derrumbe", "obra", "bloqueo", "trafico", "desvio", "clima", "otro"}
SEVERIDADES = {"baja", "media", "alta"}


def _ahora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def puntos_de_geometria(geom: dict | None) -> list[Punto]:
    if not geom:
        return []
    tipo = geom.get("type")
    coords = geom.get("coordinates")
    if tipo == "Point" and coords:
        return [(coords[0], coords[1])]
    if tipo == "LineString" and coords:
        return [(c[0], c[1]) for c in coords]
    if tipo == "Polygon" and coords:
        pts: list[Punto] = []
        for anillo in coords:
            pts.extend((c[0], c[1]) for c in anillo)
        return pts
    if tipo == "MultiPolygon" and coords:
        pts = []
        for poly in coords:
            for anillo in poly:
                pts.extend((c[0], c[1]) for c in anillo)
        return pts
    return []


def _dist_geometrias(a: list[Punto], b: list[Punto]) -> float:
    """Distancia aproximada (m) entre dos conjuntos de puntos."""
    if not a or not b:
        return float("inf")
    mejor = float("inf")
    for p in a:
        d = geo.distancia_punto_a_linea_m(p, b)
        if d < mejor:
            mejor = d
    for p in b:
        d = geo.distancia_punto_a_linea_m(p, a)
        if d < mejor:
            mejor = d
    return mejor


def _bbox_cruzan(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


@dataclass
class Alerta:
    id: str
    tipo: str
    titulo: str
    descripcion: str = ""
    severidad: str = "media"
    retraso_seg: float = 0.0
    lineas_afectadas: list[str] = field(default_factory=list)
    geometria: dict[str, Any] | None = None
    vigencia: dict[str, Any] = field(default_factory=lambda: {"desde": None, "hasta": None})
    fuente: str = "ConectaCB"
    activo: bool = True
    creado_en: str = field(default_factory=_ahora_iso)
    actualizado_en: str = field(default_factory=_ahora_iso)

    def vigente(self, ahora: datetime | None = None) -> bool:
        if not self.activo:
            return False
        ahora = ahora or datetime.now()
        desde = (self.vigencia or {}).get("desde")
        hasta = (self.vigencia or {}).get("hasta")
        if desde:
            try:
                if ahora < datetime.fromisoformat(desde):
                    return False
            except ValueError:
                pass
        if hasta:
            try:
                if ahora > datetime.fromisoformat(hasta):
                    return False
            except ValueError:
                pass
        return True

    def afecta_linea(self, linea, radio_m: float) -> bool:
        if self.lineas_afectadas and linea.id in self.lineas_afectadas:
            return True
        if not self.geometria:
            return False
        alerta_pts = puntos_de_geometria(self.geometria)
        # Descarte rapido: con cientos de rutas del SITP, casi todas quedan lejos de la alerta.
        if alerta_pts and not _bbox_cruzan(geo.bbox_expandida(geo.bbox(alerta_pts), radio_m), linea.bbox):
            return False
        return _dist_geometrias(alerta_pts, list(linea.geometria)) <= radio_m

    def afecta_geometria(self, puntos: list[Punto], radio_m: float) -> bool:
        if not self.geometria:
            return False
        alerta_pts = puntos_de_geometria(self.geometria)
        return _dist_geometrias(alerta_pts, puntos) <= radio_m

    def resumen(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            "severidad": self.severidad,
            "retraso_seg": self.retraso_seg,
            "lineas_afectadas": self.lineas_afectadas,
            "geometria": self.geometria,
            "vigencia": self.vigencia,
            "fuente": self.fuente,
            "activo": self.activo,
        }

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)


class AlmacenAlertas:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._alertas: list[Alerta] = []
        self._cargar()

    def _cargar(self) -> None:
        self._alertas = []
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for item in data.get("alertas", []):
            campos = {f.name for f in fields(Alerta)}
            limpio = {k: v for k, v in item.items() if k in campos}
            limpio["id"] = str(item.get("id"))
            self._alertas.append(Alerta(**limpio))

    def _guardar(self) -> None:
        self.path.write_text(
            json.dumps(
                {"alertas": [a.a_dict() for a in self._alertas]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _siguiente_id(self) -> str:
        n = 1
        existentes = {a.id for a in self._alertas}
        while f"AL-{n:03d}" in existentes:
            n += 1
        return f"AL-{n:03d}"

    def listar(
        self,
        activas: bool | None = None,
        tipo: str | None = None,
        solo_vigentes: bool = False,
    ) -> list[Alerta]:
        resultado = list(self._alertas)
        if activas is not None:
            resultado = [a for a in resultado if a.activo == activas]
        if solo_vigentes:
            resultado = [a for a in resultado if a.vigente()]
        if tipo:
            resultado = [a for a in resultado if a.tipo == tipo]
        return resultado

    def obtener(self, id_alerta: str) -> Alerta | None:
        for a in self._alertas:
            if a.id == id_alerta:
                return a
        return None

    def crear(self, datos: dict[str, Any]) -> Alerta:
        with self._lock:
            alerta = Alerta(
                id=str(datos.get("id") or self._siguiente_id()),
                tipo=str(datos.get("tipo") or "otro"),
                titulo=str(datos.get("titulo") or "Novedad"),
                descripcion=str(datos.get("descripcion") or ""),
                severidad=str(datos.get("severidad") or "media"),
                retraso_seg=float(datos.get("retraso_seg") or 0),
                lineas_afectadas=list(datos.get("lineas_afectadas") or []),
                geometria=datos.get("geometria"),
                vigencia=datos.get("vigencia") or {"desde": None, "hasta": None},
                fuente=str(datos.get("fuente") or "ConectaCB"),
                activo=bool(datos.get("activo", True)),
            )
            self._alertas.append(alerta)
            self._guardar()
            return alerta

    def actualizar(self, id_alerta: str, datos: dict[str, Any]) -> Alerta | None:
        with self._lock:
            alerta = self.obtener(id_alerta)
            if alerta is None:
                return None
            for campo in (
                "tipo",
                "titulo",
                "descripcion",
                "severidad",
                "lineas_afectadas",
                "geometria",
                "vigencia",
                "fuente",
                "activo",
            ):
                if campo in datos and datos[campo] is not None:
                    setattr(alerta, campo, datos[campo])
            if "retraso_seg" in datos and datos["retraso_seg"] is not None:
                alerta.retraso_seg = float(datos["retraso_seg"])
            alerta.actualizado_en = _ahora_iso()
            self._guardar()
            return alerta

    def eliminar(self, id_alerta: str) -> bool:
        with self._lock:
            antes = len(self._alertas)
            self._alertas = [a for a in self._alertas if a.id != id_alerta]
            if len(self._alertas) != antes:
                self._guardar()
                return True
            return False

    def activas_para_linea(self, linea, radio_m: float | None = None) -> list[Alerta]:
        radio = radio_m if radio_m is not None else settings.alerta_radio_afectacion_m
        return [a for a in self._alertas if a.vigente() and a.afecta_linea(linea, radio)]

    def activas_para_geometria(
        self, puntos: list[Punto], radio_m: float | None = None
    ) -> list[Alerta]:
        radio = radio_m if radio_m is not None else settings.alerta_radio_afectacion_m
        return [a for a in self._alertas if a.vigente() and a.afecta_geometria(puntos, radio)]

    def cerca(self, lon: float, lat: float, radio_m: float) -> list[Alerta]:
        p = (lon, lat)
        resultado: list[tuple[float, Alerta]] = []
        for a in self._alertas:
            pts = puntos_de_geometria(a.geometria)
            if not pts:
                continue
            d = _dist_geometrias([p], pts)
            if d <= radio_m:
                resultado.append((d, a))
        resultado.sort(key=lambda t: t[0])
        return [a for _, a in resultado]


_almacen: AlmacenAlertas | None = None


def almacen_alertas() -> AlmacenAlertas:
    global _almacen
    if _almacen is None:
        _almacen = AlmacenAlertas(settings.alertas_path)
    return _almacen
