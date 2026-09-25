"""Utilidades de fecha/hora y horarios de servicio."""
from __future__ import annotations

from datetime import datetime

DIAS = ["L", "M", "X", "J", "V", "S", "D"]


def dia_letra(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return DIAS[dt.weekday()]


def hora_actual(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%H:%M")


def parse_hora(hora: str | None) -> int | None:
    """Convierte 'HH:MM' a minutos desde medianoche. None si no es valido."""
    if not hora:
        return None
    try:
        partes = hora.strip().split(":")
        h = int(partes[0])
        m = int(partes[1]) if len(partes) > 1 else 0
    except (ValueError, IndexError):
        return None
    if not (0 <= h <= 24 and 0 <= m < 60):
        return None
    return h * 60 + m


def dentro_horario(horario: dict | None, hora: str | None, dia: str | None) -> bool:
    """True si el servicio esta activo a esa hora/dia. Sin horario => siempre."""
    if not horario:
        return True
    dias = horario.get("dias")
    if dias and dia and dia.upper() not in [d.upper() for d in dias]:
        return False
    ini = parse_hora(horario.get("ini"))
    fin = parse_hora(horario.get("fin"))
    h = parse_hora(hora) if hora else None
    if ini is None or fin is None or h is None:
        return True
    if ini <= fin:
        return ini <= h <= fin
    # Horario que cruza medianoche (p. ej. 22:00 - 05:00).
    return h >= ini or h <= fin


def espera_por_frecuencia(frecuencia_min: float | None, fallback_seg: float) -> float:
    """Espera esperada en segundos: media cabeza de frecuencia, o el fallback."""
    if frecuencia_min and frecuencia_min > 0:
        return frecuencia_min * 60.0 / 2.0
    return fallback_seg
