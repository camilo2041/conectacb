"""Modelos Pydantic de entrada y salida."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Perfil = Literal["driving", "walking", "cycling"]


class Coordenada(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitud (WGS84)")
    lon: float = Field(..., ge=-180, le=180, description="Longitud (WGS84)")


class Pesos(BaseModel):
    """Pesos para el costo ponderado. Si se omite, se usa comparacion lexicografica."""

    tiempo: float = Field(1.0, ge=0, description="Peso del tiempo (segundos)")
    tarifa: float = Field(0.0, ge=0, description="Peso de la tarifa (COP)")
    transbordos: float = Field(0.0, ge=0, description="Peso por transbordo")


class OpcionesRuteo(BaseModel):
    max_transbordos: int = Field(2, ge=0, le=5)
    radio_acceso_m: float = Field(1500.0, ge=100, le=10000)
    max_paradas_por_extremo: int = Field(6, ge=1, le=30)


class RutaRequest(BaseModel):
    origen: Coordenada | None = Field(
        None, description="Coordenadas del origen. Alternativa: `origen_texto`."
    )
    destino: Coordenada | None = Field(
        None, description="Coordenadas del destino. Alternativa: `destino_texto`."
    )
    origen_texto: str | None = Field(
        None, description="Nombre/barrio/direccion del origen (se geocodifica)."
    )
    destino_texto: str | None = Field(
        None, description="Nombre/barrio/direccion del destino (se geocodifica)."
    )
    perfil: Perfil = "driving"
    usar_directo: bool = Field(
        True,
        description="Incluir la ruta directa en auto por la red vial como opcion.",
    )
    usar_informales: bool = True
    usar_formales: bool = True
    hora: str | None = Field(
        None,
        description="Hora local 'HH:MM' para calcular esperas y validar servicio. Por defecto, la hora actual.",
    )
    dia: str | None = Field(
        None,
        description="Dia de la semana (L,M,X,J,V,S,D). Por defecto, el dia actual.",
    )
    pesos: Pesos | None = Field(
        default=None,
        description="Si es null, se ordena por (tiempo, tarifa, transbordos).",
    )
    opciones: OpcionesRuteo = Field(default_factory=OpcionesRuteo)


class NovedadResumen(BaseModel):
    id: str
    tipo: str
    titulo: str
    severidad: str
    retraso_seg: float
    lineas_afectadas: list[str] = Field(default_factory=list)


class Tramo(BaseModel):
    modo: Literal["acceso", "informal", "formal", "cable", "directo"]
    linea: str | None = None
    desde: Coordenada
    hasta: Coordenada
    distancia_m: float
    duracion_seg: float
    tarifa_cop: float
    geometria: dict[str, Any]


class ZonaResumen(BaseModel):
    nombre: str | None = None
    zona: str | None = None
    color: str | None = None
    letra: str | None = None
    rango: str | None = None


class RutaResumen(BaseModel):
    distancia_m: float
    duracion_seg: float
    tarifa_total_cop: float
    transbordos: int
    geometria: dict[str, Any]
    tramos: list[Tramo]
    zonas: list[ZonaResumen]
    informales_usadas: list[str] = Field(default_factory=list)
    formales_usadas: list[str] = Field(default_factory=list)
    novedades: list[NovedadResumen] = Field(default_factory=list)


class RutaResponse(RutaResumen):
    alternativas: list[RutaResumen] = Field(default_factory=list)


class ZonaUbicacionResponse(BaseModel):
    punto: Coordenada
    zona: ZonaResumen | None = None
    zonas_cercanas: list[ZonaResumen] = Field(default_factory=list)


# --- Alertas / novedades ---
class AlertaBase(BaseModel):
    tipo: Literal["derrumbe", "obra", "bloqueo", "trafico", "desvio", "clima", "otro"] = "otro"
    titulo: str
    descripcion: str = ""
    severidad: Literal["baja", "media", "alta"] = "media"
    retraso_seg: float = Field(0.0, ge=0)
    lineas_afectadas: list[str] = Field(default_factory=list)
    geometria: dict[str, Any] | None = None
    vigencia: dict[str, Any] = Field(default_factory=lambda: {"desde": None, "hasta": None})
    fuente: str = "ConectaCB"
    activo: bool = True


class AlertaCreate(AlertaBase):
    id: str | None = None


class AlertaUpdate(BaseModel):
    tipo: Literal["derrumbe", "obra", "bloqueo", "trafico", "desvio", "clima", "otro"] | None = None
    titulo: str | None = None
    descripcion: str | None = None
    severidad: Literal["baja", "media", "alta"] | None = None
    retraso_seg: float | None = Field(None, ge=0)
    lineas_afectadas: list[str] | None = None
    geometria: dict[str, Any] | None = None
    vigencia: dict[str, Any] | None = None
    fuente: str | None = None
    activo: bool | None = None


class Alerta(AlertaBase):
    id: str
    creado_en: str
    actualizado_en: str
    lineas_afectadas_efectivas: list[str] = Field(
        default_factory=list,
        description=(
            "Lineas a las que el ruteo aplica la alerta: las declaradas en `lineas_afectadas` "
            "mas las que pasan a menos de `RUTAS_ALERTA_RADIO_AFECTACION_M` de su geometria."
        ),
    )


# --- Lugares / geocoding ---
class LugarResumen(BaseModel):
    nombre: str
    tipo: str
    lat: float
    lon: float
    alias: list[str] = Field(default_factory=list)


class GeocodificacionResponse(BaseModel):
    consulta: str
    resultados: list[LugarResumen] = Field(default_factory=list)


# --- Asistente en lenguaje natural ---
class AsistenteRequest(BaseModel):
    texto: str = Field(..., description="Pregunta en lenguaje natural, p.ej. 'como llego de Quiba a Portal Tunal'")
    origen: Coordenada | None = None
    destino: Coordenada | None = None
    perfil: Perfil = "driving"
    usar_directo: bool = True
    hora: str | None = None
    dia: str | None = None


class AsistenteResponse(BaseModel):
    texto: str
    origen: LugarResumen | None = None
    destino: LugarResumen | None = None
    respuesta: str
    ruta: RutaResponse | None = None

