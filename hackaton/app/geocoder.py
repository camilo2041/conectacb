"""Geocodificacion por gazetteer de lugares (barrios, veredas, estaciones)."""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from .config import settings


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().strip().split())


@dataclass
class Lugar:
    nombre: str
    tipo: str
    lat: float
    lon: float
    alias: list[str] = field(default_factory=list)

    def resumen(self) -> dict:
        return {
            "nombre": self.nombre,
            "tipo": self.tipo,
            "lat": self.lat,
            "lon": self.lon,
            "alias": self.alias,
        }


class Gazetteer:
    def __init__(self, lugares: list[Lugar]):
        self.lugares = lugares
        self._indice: list[tuple[str, Lugar]] = []
        for lugar in lugares:
            self._indice.append((normalizar(lugar.nombre), lugar))
            for a in lugar.alias:
                self._indice.append((normalizar(a), lugar))

    def listar(self) -> list[Lugar]:
        return list(self.lugares)

    def buscar(self, consulta: str, limite: int = 5) -> list[tuple[float, Lugar]]:
        q = normalizar(consulta)
        if not q:
            return []
        puntajes: dict[str, tuple[float, Lugar]] = {}
        for termino, lugar in self._indice:
            clave = lugar.nombre
            score = 0.0
            if termino == q:
                score = 1.0
            elif termino.startswith(q) or q.startswith(termino):
                score = 0.9
            elif q in termino:
                score = 0.8
            else:
                score = SequenceMatcher(None, q, termino).ratio()
                if score < 0.6:
                    continue
            actual = puntajes.get(clave)
            if actual is None or score > actual[0]:
                puntajes[clave] = (score, lugar)
        ordenado = sorted(puntajes.values(), key=lambda t: t[0], reverse=True)
        return ordenado[:limite]

    def resolver(self, consulta: str) -> Lugar | None:
        resultados = self.buscar(consulta, limite=1)
        return resultados[0][1] if resultados else None


def resolver_lugar(consulta: str, gaz: "Gazetteer | None" = None, permitir_externo: bool = True) -> Lugar | None:
    """Resuelve un texto a un lugar: primero el gazetteer local, luego OSM (Photon)."""
    gaz = gaz or cargar_lugares()
    lugar = gaz.resolver(consulta)
    if lugar is not None:
        return lugar
    if permitir_externo:
        from .geocoder_externo import buscar_externo

        externos = buscar_externo(consulta, limite=1)
        if externos:
            return externos[0]
    return None


def _cargar(path: Path) -> Gazetteer:
    if not path.exists():
        return Gazetteer([])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Gazetteer([])
    lugares = [
        Lugar(
            nombre=str(item["nombre"]),
            tipo=str(item.get("tipo") or "lugar"),
            lat=float(item["lat"]),
            lon=float(item["lon"]),
            alias=list(item.get("alias") or []),
        )
        for item in data.get("lugares", [])
        if "nombre" in item and "lat" in item and "lon" in item
    ]
    return Gazetteer(lugares)


@lru_cache(maxsize=1)
def cargar_lugares(path: str | None = None) -> Gazetteer:
    return _cargar(Path(path) if path else settings.lugares_path)
