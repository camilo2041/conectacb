"""Configuracion de tarifas e integracion del sistema."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import settings

_DEFECTO = {
    "moneda": "COP",
    "sistema_integrado": "TransMilenio",
    "ventana_integracion_min": 125,
    "tipos_integrados": ["cable", "formal", "troncal", "alimentador", "sitp", "urbano"],
    "tarifa_base_troncal": 3550,
}


@lru_cache(maxsize=1)
def cargar_tarifas(path: str | None = None) -> dict:
    ruta = Path(path) if path else settings.tarifas_path
    if not ruta.exists():
        return dict(_DEFECTO)
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(_DEFECTO)
    return {**_DEFECTO, **data}
