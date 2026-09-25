"""Pruebas de humo de la API (OSRM simulado, sin red)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.osrm import RutaOSRM, cliente_osrm

client = TestClient(app)


@pytest.fixture(autouse=True)
def _osrm_falso(monkeypatch):
    def fake_ruta(a, b, perfil="driving", permitir_respaldo=True):
        return RutaOSRM(
            distancia_m=8000.0,
            duracion_seg=6000.0,  # lento a proposito para forzar el uso de informales
            geometria=[a, b],
            perfil=perfil,
        )

    monkeypatch.setattr(cliente_osrm, "ruta", fake_ruta)
    # Sin red para el geocoder externo en las pruebas.
    from app.config import settings

    monkeypatch.setattr(settings, "geocoder_externo", False)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["zonas"] == 9
    assert data["rutas_informales"] >= 1
    assert data["rutas_formales"] >= 1


def test_zonas():
    r = client.get("/zonas")
    assert r.status_code == 200
    assert r.json()["type"] == "FeatureCollection"


def test_zona_ubicacion():
    r = client.get("/zonas/ubicacion", params={"lat": 4.60, "lon": -74.08})
    assert r.status_code == 200
    data = r.json()
    assert data["zona"]["nombre"] == "Neutra"


def test_rutas_informales():
    r = client.get("/rutas-informales")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_rutas_formales():
    r = client.get("/rutas-formales")
    assert r.status_code == 200
    rutas = r.json()["rutas"]
    assert any(x["modo"] == "cable" for x in rutas)


def test_ruta_combina_cable_e_informal():
    body = {
        "origen": {"lat": 4.575, "lon": -74.180},             # Cazuca (real)
        "destino": {"lat": 4.555691, "lon": -74.147484},      # Juan Pablo II (real)
        "usar_directo": False,
        "hora": "12:00",
    }
    r = client.post("/ruta", json=body)
    assert r.status_code == 200
    data = r.json()
    assert "TMC-01" in data["formales_usadas"]
    assert "CB-07" in data["informales_usadas"]
    modos = [t["modo"] for t in data["tramos"]]
    assert "cable" in modos
    assert "informal" in modos


def test_ruta_multimodal_usa_informal():
    body = {
        "origen": {"lat": 4.757, "lon": -74.083},
        "destino": {"lat": 4.615, "lon": -74.080},
        "hora": "12:00",
    }
    r = client.post("/ruta", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["geometria"]["type"] == "LineString"
    assert data["duracion_seg"] > 0
    assert "INF-001" in data["informales_usadas"]
    assert data["tarifa_total_cop"] > 0
    assert len(data["tramos"]) >= 1
    assert len(data["zonas"]) >= 1


def test_ruta_sin_informales_es_directa():
    body = {
        "origen": {"lat": 4.757, "lon": -74.083},
        "destino": {"lat": 4.615, "lon": -74.080},
        "usar_informales": False,
        "hora": "12:00",
    }
    r = client.post("/ruta", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["informales_usadas"] == []
    assert data["tramos"][0]["modo"] == "directo"
    assert data["tarifa_total_cop"] == 0


def test_lineas_y_horarios():
    lineas = client.get("/lineas").json()
    assert lineas["total"] >= 3
    horario = client.get("/lineas/TMC-01/horario", params={"hora": "12:00"}).json()
    assert horario["activo"] is True
    assert horario["espera_seg"] > 0
    h = client.get("/horarios", params={"hora": "03:00"}).json()
    assert h["total"] >= 3


def test_tarifas():
    data = client.get("/tarifas").json()
    assert "tipos_integrados" in data
    assert any(l["id"] == "TMC-01" and l["integrado"] for l in data["lineas"])


def test_geocodificar():
    r = client.get("/geocodificar", params={"q": "quiba"})
    assert r.status_code == 200
    nombres = [x["nombre"] for x in r.json()["resultados"]]
    assert "Quiba" in nombres


def test_ruta_con_nombres_de_lugar():
    body = {
        "origen_texto": "Quiba",
        "destino_texto": "Portal Tunal",
        "usar_directo": False,
        "hora": "12:00",
    }
    r = client.post("/ruta", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["duracion_seg"] > 0
    assert data["geometria"]["type"] == "LineString"


def test_ruta_texto_no_encontrado():
    r = client.post(
        "/ruta",
        json={"origen_texto": "lugar inexistente zzz", "destino_texto": "Portal Tunal"},
    )
    assert r.status_code == 422


def test_novedades_afectan_ruta():
    body = {
        "origen": {"lat": 4.513704, "lon": -74.164648},  # Quiba (real)
        "destino": {"lat": 4.575, "lon": -74.180},        # Cazuca (real)
        "usar_directo": False,
        "hora": "12:00",
    }
    r = client.post("/ruta", json=body)
    assert r.status_code == 200
    data = r.json()
    assert "CB-05" in data["informales_usadas"]
    ids = [n["id"] for n in data["novedades"]]
    assert "AL-001" in ids
    assert any(n["retraso_seg"] > 0 for n in data["novedades"])


def test_tarifa_integrada_cable_troncal():
    body = {
        "origen": {"lat": 4.550082, "lon": -74.158767},  # Mirador del Paraiso (real)
        "destino": {"lat": 4.5987, "lon": -74.0755},     # Las Aguas (real)
        "usar_directo": False,
        "hora": "12:00",
    }
    data = client.post("/ruta", json=body).json()
    assert {"TMC-01", "TMC-02"}.issubset(set(data["formales_usadas"]))
    # Cable (3200) + troncal integrada (0) = 3200
    assert data["tarifa_total_cop"] == 3200
    tarifas = {t["linea"]: t["tarifa_cop"] for t in data["tramos"] if t["linea"]}
    assert tarifas["TMC-02"] == 0


def test_asistente_lenguaje_natural():
    body = {"texto": "como llego de Cazuca a Las Aguas", "usar_directo": False, "hora": "12:00"}
    r = client.post("/asistente", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["origen"]["nombre"].startswith("Cazuca")
    assert data["destino"]["nombre"] == "Las Aguas"
    assert data["ruta"] is not None
    assert "min" in data["respuesta"]


def test_cable_pilonas():
    r = client.get("/cable/pilonas")
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 23
    assert all(f["geometry"]["type"] == "Point" for f in data["features"])


def test_ruta_mapa_y_capas():
    body = {
        "origen": {"lat": 4.575, "lon": -74.180},
        "destino": {"lat": 4.569675, "lon": -74.139249},
        "usar_directo": False,
        "hora": "12:00",
    }
    mapa = client.post("/ruta/mapa", json=body).json()
    assert mapa["type"] == "FeatureCollection"
    assert any(f["properties"]["capa"] == "ruta" for f in mapa["features"])
    capas = client.get("/capas").json()
    tipos = {f["properties"]["capa"] for f in capas["features"]}
    assert {"zona", "linea", "alerta", "pilona"}.issubset(tipos)


MIRADOR = (4.550082, -74.158767)
JUAN_PABLO_II = (4.555691, -74.147484)


def _dist_m(coord: dict, punto: tuple[float, float]) -> float:
    from app import geo

    return geo.haversine_m(coord["lat"], coord["lon"], punto[0], punto[1])


def test_tramo_en_sentido_contrario_invierte_geometria():
    from app.informal import LineaInformal

    geometria = [(0.0, 0.0), (0.001, 0.0), (0.002, 0.0)]
    lin = LineaInformal(
        id="T", nombre="T", modo="colectivo", tarifa=0, tiempo_espera_seg=0, frecuencia_min=None,
        horario={}, velocidad_kmh=20, geometria=geometria, paradas=list(geometria), indices_paradas=[0, 1, 2],
    )
    ida, dist_ida, dur_ida = lin.tramo(0, 2)
    vuelta, dist_vuelta, dur_vuelta = lin.tramo(2, 0)
    assert ida == geometria
    assert vuelta == list(reversed(geometria))
    assert (dist_vuelta, dur_vuelta) == (dist_ida, dur_ida)


def test_paradas_del_cable_caen_en_sus_estaciones():
    from app import geo
    from app.informal import cargar_formales

    cable = next(l for l in cargar_formales().lineas if l.id == "TMC-01")
    for parada, idx in zip(cable.paradas, cable.indices_paradas):
        vertice = cable.geometria[idx]
        assert geo.haversine_m(parada[1], parada[0], vertice[1], vertice[0]) < 1.0


def test_tramo_de_cable_va_en_el_sentido_del_viaje():
    body = {
        "origen": {"lat": 4.575, "lon": -74.180},  # Cazuca: toma el cable en Mirador del Paraiso
        "destino": {"lat": JUAN_PABLO_II[0], "lon": JUAN_PABLO_II[1]},
        "usar_directo": False,
        "hora": "12:00",
    }
    data = client.post("/ruta", json=body).json()
    cable = next(t for t in data["tramos"] if t["modo"] == "cable")
    assert _dist_m(cable["desde"], MIRADOR) < 5
    assert _dist_m(cable["hasta"], JUAN_PABLO_II) < 5
    inicio, fin = cable["geometria"]["coordinates"][0], cable["geometria"]["coordinates"][-1]
    assert inicio == [cable["desde"]["lon"], cable["desde"]["lat"]]
    assert fin == [cable["hasta"]["lon"], cable["hasta"]["lat"]]


@pytest.mark.parametrize(
    "origen, destino",
    [
        ((4.575, -74.180), JUAN_PABLO_II),                 # Cazuca -> Juan Pablo II (cable de bajada)
        (JUAN_PABLO_II, (4.575, -74.180)),                 # y de regreso (cable de subida)
        ((4.513704, -74.164648), (4.569675, -74.139249)),  # Quiba -> Portal Tunal
        (MIRADOR, (4.5987, -74.0755)),                     # Mirador -> Las Aguas (cable + troncal)
    ],
)
def test_tramos_encadenados(origen, destino):
    body = {
        "origen": {"lat": origen[0], "lon": origen[1]},
        "destino": {"lat": destino[0], "lon": destino[1]},
        "usar_directo": False,
        "hora": "12:00",
    }
    tramos = client.post("/ruta", json=body).json()["tramos"]
    assert tramos, "debe haber ruta"
    for anterior, siguiente in zip(tramos, tramos[1:]):
        salto = _dist_m(anterior["hasta"], (siguiente["desde"]["lat"], siguiente["desde"]["lon"]))
        assert salto < 1.0, f"{anterior['modo']} {anterior['linea']} -> {siguiente['modo']} {siguiente['linea']}: salto de {salto:.0f} m"


def test_alertas_informan_lineas_efectivas():
    alertas = {a["id"]: a for a in client.get("/alertas").json()}
    # Declaradas explicitamente.
    assert {"CB-05", "CB-09"}.issubset(alertas["AL-001"]["lineas_afectadas_efectivas"])
    # Sin lineas declaradas, pero a menos de 150 m de la troncal: el ruteo se la aplica.
    assert alertas["AL-003"]["lineas_afectadas"] == []
    assert "TMC-02" in alertas["AL-003"]["lineas_afectadas_efectivas"]


def test_alertas_crud(monkeypatch, tmp_path):
    from app import alertas as mod

    almacen = mod.AlmacenAlertas(tmp_path / "alertas.json")
    monkeypatch.setattr(mod, "_almacen", almacen)

    creada = client.post(
        "/alertas",
        json={"tipo": "obra", "titulo": "Prueba", "retraso_seg": 120, "lineas_afectadas": ["CB-01"]},
    )
    assert creada.status_code == 201
    ida = creada.json()["id"]
    assert client.get(f"/alertas/{ida}").status_code == 200
    assert any(a["id"] == ida for a in client.get("/alertas").json())

    actualizada = client.put(f"/alertas/{ida}", json={"activo": False})
    assert actualizada.json()["activo"] is False

    assert client.delete(f"/alertas/{ida}").status_code == 200
    assert client.get(f"/alertas/{ida}").status_code == 404

