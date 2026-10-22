#!/usr/bin/env python3
"""
fetch_osm.py — Acquisizione dati pubblici OpenStreetMap per l'edificio di
Via Domenico Berra 10/12/14, Milano (commessa "modellazione-3D").

Produce:
  - una sintesi a terminale (civici, edifici associati, dimensioni dedotte);
  - params/edificio_berra_osm.json: dati normalizzati con stato del dato.

Fonti: Nominatim + Overpass API (© OpenStreetMap contributors, licenza ODbL 1.0).
ATTENZIONE: dato DOCUMENTATO da fonte pubblica cartografica, NON rilievo
verificato. Le dimensioni in metri sono DEDOTTE da coordinate geografiche
(proiezione equirettangolare locale, incertezza tipica OSM: 1-5 m).
Solo stdlib Python, nessuna dipendenza esterna.
"""
from __future__ import annotations

import json
import math
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

UA = {"User-Agent": "modellazione-3D-berra/0.1 (workspace BIM locale)"}
R_EARTH = 6_371_000.0
STREET = "Via Domenico Berra"
NUMBERS = ["10", "12", "14"]
CITY = "Milano"
RADIUS_M = 350          # raggio di ricerca Overpass attorno al civico 12
ASSOC_THRESHOLD_M = 10  # distanza max nodo civico -> edificio per associazione

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "params" / "edificio_berra_osm.json"


def http_json(url: str, data: bytes | None = None):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def nominatim_lookup(number: str) -> dict | None:
    q = urllib.parse.urlencode({
        "street": f"{STREET} {number}", "city": CITY, "country": "Italy",
        "format": "json", "limit": 1,
    })
    res = http_json(f"https://nominatim.openstreetmap.org/search?{q}")
    if not res:
        return None
    r = res[0]
    return {"lat": float(r["lat"]), "lon": float(r["lon"]),
            "display_name": r.get("display_name", ""),
            "osm_type": r["osm_type"], "osm_id": r["osm_id"]}


def overpass(query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    return http_json("https://overpass-api.de/api/interpreter", data=data)


class Proj:
    """Proiezione equirettangolare locale, origine al civico 12.
    Accettabile su scala di isolato (errore < 0,1% entro ~1 km)."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = lat0, lon0
        self._k = math.cos(math.radians(lat0))

    def xy(self, lat: float, lon: float) -> tuple[float, float]:
        return ((lon - self.lon0) * self._k * math.radians(R_EARTH),
                (lat - self.lat0) * math.radians(R_EARTH))


def point_in_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


def _dist_seg(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def dist_point_poly(px, py, poly) -> float:
    return min(_dist_seg(px, py, *poly[i], *poly[(i + 1) % len(poly)])
               for i in range(len(poly)))


def poly_metrics(poly) -> tuple[float, float, list[float]]:
    area, per, edges = 0.0, 0.0, []
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        area += x1 * y2 - x2 * y1
        length = math.hypot(x2 - x1, y2 - y1)
        per += length
        edges.append(round(length, 2))
    return abs(area) / 2.0, per, edges


def main() -> int:
    print(f"== Acquisizione OSM: {STREET} {'/'.join(NUMBERS)}, {CITY} ==\n")

    # 1) Geocodifica Nominatim dei tre civici
    geocoded: dict[str, dict | None] = {}
    for n in NUMBERS:
        geocoded[n] = nominatim_lookup(n)
        print(f"[Nominatim] civico {n}: " +
              (f"{geocoded[n]['lat']}, {geocoded[n]['lon']}" if geocoded[n]
               else "non trovato"))

    ref = geocoded.get("12") or next((v for v in geocoded.values() if v), None)
    if ref is None:
        print("ERRORE: nessun civico geocodificato, impossibile proseguire.")
        return 1
    lat0, lon0 = ref["lat"], ref["lon"]

    # 2) Overpass: nodi indirizzo + edifici nel raggio
    query = f"""[out:json][timeout:90];
(
  node["addr:housenumber"](around:{RADIUS_M},{lat0},{lon0});
  way["building"](around:{RADIUS_M},{lat0},{lon0});
  relation["building"](around:{RADIUS_M},{lat0},{lon0});
);
out body;>;out skel qt;"""
    data = overpass(query)
    nodes = {e["id"]: (e["lat"], e["lon"]) for e in data["elements"]
             if e["type"] == "node" and "lat" in e}

    addr_nodes = []
    buildings = []
    for e in data["elements"]:
        tags = e.get("tags", {})
        if e["type"] == "node" and "berra" in tags.get("addr:street", "").lower():
            addr_nodes.append({
                "osm_id": e["id"], "lat": e["lat"], "lon": e["lon"],
                "number": tags.get("addr:housenumber", ""),
                "street": tags.get("addr:street", "")})
        elif e["type"] == "way" and "building" in tags:
            coords = [nodes[nid] for nid in e["nodes"] if nid in nodes]
            if len(coords) > 1 and coords[0] == coords[-1]:
                coords = coords[:-1]  # rimuove chiusura duplicata
            if len(coords) >= 3:
                buildings.append({"way_id": e["id"], "tags": tags, "coords": coords})

    print(f"\n[Overpass] nodi indirizzo su Via Berra: {len(addr_nodes)} | "
          f"edifici nel raggio: {len(buildings)}")

    # 3) Proiezione metrica e metriche impronta
    prj = Proj(lat0, lon0)
    for b in buildings:
        b["poly_m"] = [tuple(round(v, 3) for v in prj.xy(*c)) for c in b["coords"]]
        area, per, edges = poly_metrics(b["poly_m"])
        b["area_m2"] = round(area, 1)
        b["perimetro_m"] = round(per, 2)
        b["lati_m"] = edges

    # 4) Associazione civico -> edificio (contenimento o prossimità)
    civici_out = []
    matched_ids: list[int] = []
    for n in NUMBERS:
        point, fonte = None, None
        if geocoded.get(n):
            point = (geocoded[n]["lat"], geocoded[n]["lon"])
            fonte = f"nominatim:{geocoded[n]['osm_type']}/{geocoded[n]['osm_id']}"
        else:
            cand = [a for a in addr_nodes if a["number"].rstrip("/ABab") == n]
            if cand:
                point = (cand[0]["lat"], cand[0]["lon"])
                fonte = f"osm:node/{cand[0]['osm_id']}"
        entry = {"civico": n, "fonte_punto": fonte,
                 "lat": point[0] if point else None,
                 "lon": point[1] if point else None,
                 "edificio_way_id": None, "metodo_associazione": None,
                 "distanza_m": None}
        if point:
            px, py = prj.xy(*point)
            best, best_d, inside = None, float("inf"), False
            for b in buildings:
                if point_in_poly(px, py, b["poly_m"]):
                    best, best_d, inside = b, 0.0, True
                    break
                d = dist_point_poly(px, py, b["poly_m"])
                if d < best_d:
                    best, best_d = b, d
            if best and (inside or best_d <= ASSOC_THRESHOLD_M):
                entry.update(edificio_way_id=best["way_id"],
                             metodo_associazione=("contenimento" if inside
                                                  else "prossimità"),
                             distanza_m=round(best_d, 2))
                if best["way_id"] not in matched_ids:
                    matched_ids.append(best["way_id"])
        civici_out.append(entry)

    # 5) Output
    def tag_summary(t):
        keys = ["building", "building:levels", "building:use", "height",
                "roof:shape", "building:material", "building:colour",
                "addr:housenumber", "addr:street"]
        return {k: t[k] for k in keys if k in t}

    edifici_out = [{
        "way_id": b["way_id"],
        "url": f"https://www.openstreetmap.org/way/{b['way_id']}",
        "tags": tag_summary(b["tags"]),
        "vertici_m": b["poly_m"],
        "lati_m": b["lati_m"],
        "area_m2": b["area_m2"],
        "perimetro_m": b["perimetro_m"],
    } for b in buildings if b["way_id"] in matched_ids]

    result = {
        "commessa": {"indirizzo": f"{STREET} {'/'.join(NUMBERS)}",
                     "comune": CITY, "stato": "Italia"},
        "acquisizione": {
            "data": str(date.today()),
            "fonti": ["nominatim.openstreetmap.org", "overpass-api.de"],
            "licenza": "© OpenStreetMap contributors, ODbL 1.0",
            "stato_dato": "A-DOCUMENTATO (fonte pubblica) per impronta/tag; "
                          "B-DEDOTTO per dimensioni metriche e associazione "
                          "civico→edificio; DA VERIFICARE con rilievo/foto.",
            "incertezza_stimata_m": "1-5 (tipica OSM)",
        },
        "origine_locale": {"lat": lat0, "lon": lon0,
                           "nota": "origine XY = posizione geocodificata civico 12"},
        "civici": civici_out,
        "edifici_associati": edifici_out,
        "altri_edifici_nel_raggio": [
            {"way_id": b["way_id"], "tags": tag_summary(b["tags"]),
             "area_m2": b["area_m2"]}
            for b in buildings if b["way_id"] not in matched_ids],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n== Civici ==")
    for c in civici_out:
        print(f"  n.{c['civico']:>3} | punto: {c['fonte_punto'] or 'MANCANTE'} | "
              f"edificio: {c['edificio_way_id'] or '?'} "
              f"({c['metodo_associazione'] or '-'}, d={c['distanza_m']} m)")
    print("\n== Edifici associati ==")
    for e in edifici_out:
        print(f"  way/{e['way_id']}: {e['tags']} | area {e['area_m2']} m² | "
              f"perimetro {e['perimetro_m']} m | lati {e['lati_m']}")
    print(f"\nScritto: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
