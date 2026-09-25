"""Carga de las pilonas del cable (trazado real) para el mapa."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import settings


@lru_cache(maxsize=1)
def cargar_pilonas(path: str | None = None) -> dict:
    ruta = Path(path) if path else settings.pilonas_path
    if not ruta.exists():
        return {"type": "FeatureCollection", "features": []}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"type": "FeatureCollection", "features": []}


def pilonas_como_capa() -> list[dict]:
    """Convierte las pilonas en Features de capa para /capas."""
    crudo = cargar_pilonas()
    features: list[dict] = []
    for f in crudo.get("features", []):
        props = dict(f.get("properties") or {})
        features.append(
            {
                "type": "Feature",
                "geometry": f.get("geometry"),
                "properties": {
                    "capa": "pilona",
                    "id_pilona": props.get("id_pilona"),
                    "num_pil": props.get("num_pil"),
                    "trazado": props.get("nom_traz"),
                    "cable": props.get("cable"),
                    "operativa": bool(props.get("esta_oper")),
                },
            }
        )
    return features
