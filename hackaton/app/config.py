"""Configuracion central de la API."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RUTAS_", env_file=".env", extra="ignore")

    # Datos
    zonas_path: Path = DATA_DIR / "Zonas_SITP.geojson"
    informales_path: Path = DATA_DIR / "rutas_informales.geojson"
    # Se pueden cargar varios archivos de rutas informales a la vez.
    informales_glob: str = str(DATA_DIR / "rutas_informales*.geojson")
    # Rutas formales (p. ej. TransMiCable).
    formales_glob: str = str(DATA_DIR / "rutas_formales*.geojson")
    # Novedades/alertas, gazetteer de lugares y tarifas.
    alertas_path: Path = DATA_DIR / "alertas.json"
    lugares_path: Path = DATA_DIR / "lugares.json"
    tarifas_path: Path = DATA_DIR / "tarifas.json"
    # Pilonas del cable (trazado real).
    pilonas_path: Path = DATA_DIR / "Pilona_cable.geojson"

    # Geocoding externo (OpenStreetMap via Photon) como respaldo del gazetteer.
    geocoder_externo: bool = True
    photon_url: str = "https://photon.komoot.io"
    geocoder_timeout_s: float = 6.0
    # Distancia (m) para considerar que una alerta afecta una linea/geometria.
    alerta_radio_afectacion_m: float = 150.0

    # OSRM (servidor publico de demostracion, fair-use)
    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_timeout_s: float = 12.0
    osrm_cache_ttl_s: float = 3600.0
    osrm_cache_max: int = 2048

    # Valores por defecto de ruteo
    radio_acceso_m: float = 1500.0
    radio_transbordo_m: float = 400.0
    max_transbordos: int = 2
    max_paradas_por_extremo: int = 6

    # Velocidades (km/h) para tramos de acceso sin OSRM
    velocidad_caminata_kmh: float = 4.8
    penalizacion_transbordo_seg: float = 240.0

    # CORS
    cors_origins: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

# Aseguramos que el directorio de datos exista.
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("RUTAS_BASE_DIR", str(BASE_DIR))
