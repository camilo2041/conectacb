"""Importa el GTFS oficial de TransMilenio (SITP) para Ciudad Bolivar.

Uso:
    python scripts/importar_gtfs.py RUTA_AL_GTFS(.zip o carpeta) [--fecha AAAA-MM-DD]

Descarga el GTFS en https://datosabiertos-transmilenio.hub.arcgis.com (coleccion "GTFS Estaticos").
Genera `data/rutas_formales_sitp.geojson` con cada variante de recorrido (ruta + trazado + paraderos)
que tenga al menos un paradero en Ciudad Bolivar: troncales, alimentadores y zonales. El recorrido
se guarda completo, para poder viajar a otras localidades. El TransMiCable se omite porque ya esta
en `rutas_formales.geojson` con su trazado de pilonas.

Por cada variante guarda:
- el trazado simplificado y la posicion de cada paradero en el,
- el tiempo acumulado entre paraderos de un viaje real de hora pico (dia habil, cerca de 7:30),
- las salidas del primer paradero (minutos desde medianoche) para dia habil, sabado y domingo.
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import math
import re
import sys
import zipfile
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SALIDA = DATA_DIR / "rutas_formales_sitp.geojson"

# Recuadro de Ciudad Bolivar (urbana y rural): el mismo que usa la web.
S, N, W, E = 4.44, 4.60, -74.21, -74.12

# Tarifa 2026 del SITP (troncal, zonal, alimentador y TransMiCable), fare_attributes.txt del GTFS.
TARIFA_DEFECTO = 3550

MODOS = {"1": "troncal", "2": "alimentador", "3": "sitp", "4": "sitp", "5": "sitp", "6": "troncal"}
AGENCIA_CABLE = "7"

TOLERANCIA_M = 6.0  # simplificacion del trazado
DIAS_TIPO = {"habil": (0, 1, 2, 3, 4), "sabado": (5,), "domingo": (6,)}


class Fuente:
    """Lee archivos del GTFS desde un .zip o una carpeta."""

    def __init__(self, ruta: Path):
        self.zip = zipfile.ZipFile(ruta) if ruta.suffix == ".zip" else None
        self.dir = ruta

    def filas(self, nombre: str):
        if self.zip:
            with self.zip.open(f"{nombre}.txt") as fh:
                yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig", newline=""))
        else:
            with open(self.dir / f"{nombre}.txt", encoding="utf-8-sig", newline="") as fh:
                yield from csv.DictReader(fh)


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def minutos(hhmmss: str) -> int:
    h, m, s = (int(x) for x in hhmmss.split(":"))
    return h * 60 + m + (1 if s >= 30 else 0)


def segundos(hhmmss: str) -> int:
    h, m, s = (int(x) for x in hhmmss.split(":"))
    return h * 3600 + m * 60 + s


def en_cb(lat: float, lon: float) -> bool:
    return S <= lat <= N and W <= lon <= E


def _dist_punto_segmento_m(p, a, b) -> float:
    # Proyeccion plana local: suficiente para tramos de pocos cientos de metros.
    kx = 111320.0 * math.cos(math.radians(p[1]))
    ky = 110540.0
    ax, ay = (a[0] - p[0]) * kx, (a[1] - p[1]) * ky
    bx, by = (b[0] - p[0]) * kx, (b[1] - p[1]) * ky
    dx, dy = bx - ax, by - ay
    largo2 = dx * dx + dy * dy
    t = 0.0 if largo2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / largo2))
    return math.hypot(ax + t * dx, ay + t * dy)


def _douglas_peucker(puntos: list, tol: float) -> list[int]:
    """Indices (relativos) de los puntos que se conservan."""
    if len(puntos) <= 2:
        return list(range(len(puntos)))
    conservar = {0, len(puntos) - 1}
    pila = [(0, len(puntos) - 1)]
    while pila:
        i, j = pila.pop()
        peor, idx = -1.0, -1
        for k in range(i + 1, j):
            d = _dist_punto_segmento_m(puntos[k], puntos[i], puntos[j])
            if d > peor:
                peor, idx = d, k
        if peor > tol:
            conservar.add(idx)
            pila.append((i, idx))
            pila.append((idx, j))
    return sorted(conservar)


def ubicar_paradas(shape: list, paradas: list) -> list[int]:
    """Indice del vertice del trazado para cada paradero, en orden (no retrocede)."""
    indices = []
    desde = 0
    for k, (lon, lat) in enumerate(paradas):
        # Busca el vertice mas cercano hacia adelante. El limite evita saltar a otra pasada de
        # la misma calle en recorridos que van y vuelven por la misma via.
        restantes = len(paradas) - k - 1
        hasta = len(shape) - restantes
        mejor, mejor_d = desde, float("inf")
        for i in range(desde, max(desde + 1, hasta)):
            d = haversine_m(lat, lon, shape[i][1], shape[i][0])
            if d < mejor_d:
                mejor, mejor_d = i, d
            elif mejor_d < 25 and d > mejor_d + 400:
                break  # ya paso por el paradero y se esta alejando
        indices.append(mejor)
        desde = mejor
    return indices


def simplificar(shape: list, indices: list[int]) -> tuple[list, list[int]]:
    """Simplifica el trazado conservando los vertices de los paraderos."""
    anclas = sorted(set([0, len(shape) - 1, *indices]))
    conservar: set[int] = set()
    for a, b in zip(anclas, anclas[1:]):
        for k in _douglas_peucker(shape[a : b + 1], TOLERANCIA_M):
            conservar.add(a + k)
    conservar.update(anclas)
    orden = sorted(conservar)
    nuevo = {viejo: i for i, viejo in enumerate(orden)}
    return [shape[i] for i in orden], [nuevo[i] for i in indices]


# Plataformas de alimentadores en los portales: el GTFS las nombra con los codigos de las rutas ("6-3_6-6").
_NOMBRE_CODIGO = re.compile(r"^\d+-\d+[A-Z]?([_ ,/]\d+-\d+[A-Z]?)*$")


def nombre_paradero(stop: dict, stops: dict) -> str:
    nombre = " ".join(stop["stop_name"].split())
    padre = stops.get(stop.get("parent_station") or "")
    if padre and _NOMBRE_CODIGO.match(nombre):
        rutas = " y ".join(re.split(r"[_ ,/]+", nombre))
        return f"{' '.join(padre['stop_name'].split())} (alimentadores {rutas})"
    return nombre


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gtfs", type=Path)
    parser.add_argument("--fecha", help="Fecha de publicacion del GTFS, para citar la fuente.")
    args = parser.parse_args()
    fuente = Fuente(args.gtfs)

    def log(msg):
        print(msg, file=sys.stderr, flush=True)

    routes = {r["route_id"]: r for r in fuente.filas("routes")}
    trips = {t["trip_id"]: t for t in fuente.filas("trips")}
    stops = {s["stop_id"]: s for s in fuente.filas("stops")}
    calendario = {}
    for c in fuente.filas("calendar"):
        dias = [i for i, k in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")) if c[k] == "1"]
        calendario[c["service_id"]] = {tipo for tipo, ds in DIAS_TIPO.items() if any(d in dias for d in ds)}
    tarifa = TARIFA_DEFECTO
    for f in fuente.filas("fare_attributes"):
        tarifa = int(float(f["price"]))

    paraderos_cb = {sid for sid, s in stops.items() if en_cb(float(s["stop_lat"]), float(s["stop_lon"]))}

    log("Buscando viajes que pasan por Ciudad Bolivar...")
    viajes_cb: set[str] = set()
    for st in fuente.filas("stop_times"):
        if st["stop_id"] in paraderos_cb:
            viajes_cb.add(st["trip_id"])
    viajes_cb = {t for t in viajes_cb if routes[trips[t]["route_id"]]["agency_id"] != AGENCIA_CABLE}
    log(f"  {len(viajes_cb)} viajes")

    log("Leyendo horarios de esos viajes...")
    paradas_viaje: dict[str, list[tuple[int, str, int]]] = collections.defaultdict(list)
    for st in fuente.filas("stop_times"):
        if st["trip_id"] in viajes_cb:
            paradas_viaje[st["trip_id"]].append((int(st["stop_sequence"]), st["stop_id"], segundos(st["arrival_time"] or st["departure_time"])))

    # Variante = misma ruta, mismo trazado y mismos paraderos en el mismo orden.
    variantes: dict[tuple, list[tuple[str, list]]] = collections.defaultdict(list)
    for trip_id, filas in paradas_viaje.items():
        filas.sort()
        t = trips[trip_id]
        clave = (t["route_id"], t["shape_id"], tuple(f[1] for f in filas))
        variantes[clave].append((trip_id, filas))
    log(f"  {len(variantes)} variantes de recorrido")

    shapes_usados = {clave[1] for clave in variantes}
    shapes: dict[str, list] = collections.defaultdict(list)
    for p in fuente.filas("shapes"):
        if p["shape_id"] in shapes_usados:
            shapes[p["shape_id"]].append((int(p["shape_pt_sequence"]), float(p["shape_pt_lon"]), float(p["shape_pt_lat"])))
    shapes = {k: [(lon, lat) for _, lon, lat in sorted(v)] for k, v in shapes.items()}

    features = []
    descartadas = 0
    contador_ruta: dict[str, int] = collections.Counter()
    for (route_id, shape_id, secuencia), viajes in sorted(variantes.items(), key=lambda kv: (routes[kv[0][0]]["route_short_name"], kv[0][0], kv[0][1])):
        ruta = routes[route_id]
        shape = shapes.get(shape_id)
        if not shape or len(secuencia) < 2:
            descartadas += 1
            continue
        coords = [(float(stops[s]["stop_lon"]), float(stops[s]["stop_lat"])) for s in secuencia]
        indices = ubicar_paradas(shape, coords)
        lejanas = sum(haversine_m(c[1], c[0], shape[i][1], shape[i][0]) > 80 for c, i in zip(coords, indices))
        if lejanas > len(coords) // 4:
            descartadas += 1  # el trazado no corresponde a los paraderos
            continue
        geometria, indices = simplificar(shape, indices)

        # Salidas por tipo de dia y viaje representativo (dia habil, salida mas cercana a 7:30).
        salidas: dict[str, list[int]] = {tipo: [] for tipo in DIAS_TIPO}
        representativo = None
        for trip_id, filas in viajes:
            inicio = filas[0][2]
            for tipo in calendario.get(trips[trip_id]["service_id"], ()):
                salidas[tipo].append(inicio // 60)
            if "habil" in calendario.get(trips[trip_id]["service_id"], ()):
                if representativo is None or abs(inicio - 27000) < abs(representativo[0][2] - 27000):
                    representativo = filas
        representativo = representativo or viajes[0][1]
        t0 = representativo[0][2]
        tiempos = [max(0, f[2] - t0) for f in representativo]
        for k in range(1, len(tiempos)):  # los tiempos no pueden retroceder
            tiempos[k] = max(tiempos[k], tiempos[k - 1])

        codigo = ruta["route_short_name"].strip()
        contador_ruta[route_id] += 1
        agencia = ruta["agency_id"]
        nombres = [nombre_paradero(stops[s], stops) for s in secuencia]
        destino = " ".join(ruta["route_long_name"].split())
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": f"SITP-{route_id}-{contador_ruta[route_id]}",
                    "nombre": f"{codigo} {destino}",
                    "codigo": codigo,
                    "destino": destino,
                    "modo": MODOS.get(agencia, "sitp"),
                    "tipo": "formal",
                    "tarifa": tarifa,
                    "integrado": True,
                    "color": f"#{ruta['route_color'].lower()}" if ruta.get("route_color") else None,
                    "sentido_unico": True,
                    "fuente": f"GTFS TransMilenio {args.fecha}" if args.fecha else "GTFS TransMilenio",
                    "paradas": [list(c) for c in coords],
                    "paradas_id": list(secuencia),
                    "paradas_nombre": nombres,
                    "indices_paradas": indices,
                    "tiempos_seg": tiempos,
                    "salidas_min": {tipo: sorted(v) for tipo, v in salidas.items()},
                },
                "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in geometria]},
            }
        )

    salida = {
        "type": "FeatureCollection",
        "name": "rutas_formales_sitp",
        "fuente": "https://datosabiertos-transmilenio.hub.arcgis.com (GTFS Estaticos)",
        "fecha_gtfs": args.fecha,
        "features": features,
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"{len(features)} variantes guardadas en {SALIDA} ({SALIDA.stat().st_size / 1e6:.1f} MB); {descartadas} descartadas")


if __name__ == "__main__":
    main()
