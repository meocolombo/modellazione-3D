from __future__ import annotations

import json
import sys
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_corte_verde_arredi_result.json")
LAYER_NAME = "BERRA_AI_CORTE_VERDE_01"


LAWN_POLYGONS = [
    # Prato principale davanti al loggiato, ricavato dalle foto sopralluogo.
    [(-32.8, 14.4), (-21.2, 14.4), (-21.2, 30.6), (-32.8, 30.6)],
    # Aiuola interna sud-ovest, lasciando un percorso centrale gia generato.
    [(-39.0, -60.0), (-32.2, -60.0), (-32.2, -24.0), (-39.0, -24.0)],
    [(-27.8, -60.0), (-20.8, -60.0), (-20.8, -24.0), (-27.8, -24.0)],
]

SHRUB_CLUSTERS = [
    (-30.8, 15.4, 1.6), (-29.9, 16.2, 1.3), (-30.2, 17.1, 1.4),
    (-25.7, 18.0, 1.8), (-24.5, 18.7, 1.5), (-26.5, 19.0, 1.4),
    (-30.0, 24.8, 1.5), (-28.7, 25.5, 1.7), (-27.8, 24.2, 1.4),
    (-35.8, -38.0, 1.6), (-34.2, -42.2, 1.4), (-24.0, -43.0, 1.5),
]

POT_POINTS = [
    (-32.0, 14.5), (-32.0, 18.2), (-32.0, 22.8), (-32.0, 27.4),
    (-22.0, 14.7), (-22.0, 30.0), (-30.0, -45.0), (-23.6, -33.0),
]


def tapir(commands, types, name, params=None):
    return commands.ExecuteAddOnCommand(types.AddOnCommandId("TapirCommand", name), params)


def coord(x, y):
    return {"x": float(x), "y": float(y)}


def point3(x, y, z):
    return {"x": float(x), "y": float(y), "z": float(z)}


def dim3(x, y, z):
    return {"x": float(x), "y": float(y), "z": float(z)}


def find_layer_index(commands, types, layer_name):
    result = tapir(commands, types, "GetAttributesByType", {"attributeType": "Layer"})
    for layer in result.get("attributes", []):
        if str(layer.get("name", "")).casefold() == layer_name.casefold():
            return int(layer.get("index"))
    return None


def create_or_get_layer(commands, types):
    existing = find_layer_index(commands, types, LAYER_NAME)
    if existing is not None:
        return existing
    tapir(
        commands,
        types,
        "CreateLayers",
        {
            "layerDataArray": [
                {
                    "name": LAYER_NAME,
                    "isHidden": False,
                    "isLocked": False,
                    "isWireframe": False,
                    "intersectionGroupNr": 111,
                }
            ],
            "overwriteExisting": False,
        },
    )
    created = find_layer_index(commands, types, LAYER_NAME)
    if created is None:
        raise RuntimeError(f"Layer non trovato dopo la creazione: {LAYER_NAME}")
    return created


def count_elements_on_layer(commands, types, layer_index):
    elements = tapir(commands, types, "GetAllElements").get("elements", [])
    details = tapir(commands, types, "GetDetailsOfElements", {"elements": elements}).get("detailsOfElements", [])
    return sum(1 for detail in details if int(detail.get("layerIndex", -1)) == int(layer_index))


def set_elements_layer(commands, types, elements, layer_index):
    if not elements:
        return None
    return tapir(
        commands,
        types,
        "SetDetailsOfElements",
        {"elementsWithDetails": [{"elementId": e["elementId"], "details": {"layerIndex": layer_index}} for e in elements]},
    )


def add_box(morphs, x, y, z, sx, sy, sz):
    morphs.append({"basePoint": point3(x, y, z), "size": dim3(sx, sy, sz)})


def add_beam(beams, x1, y1, x2, y2, z, width=0.07, height=0.055):
    beams.append(
        {
            "begCoordinate": coord(x1, y1),
            "endCoordinate": coord(x2, y2),
            "zCoordinate": float(z),
            "width": float(width),
            "height": float(height),
        }
    )


def build_lawn_slabs():
    return [
        {
            "level": 0.025,
            "thickness": 0.045,
            "polygonCoordinates": [coord(x, y) for x, y in polygon],
        }
        for polygon in LAWN_POLYGONS
    ]


def build_morphs():
    morphs = []

    # Masse arbustive/cycas semplificate: zoccolo + chioma bassa.
    for x, y, scale in SHRUB_CLUSTERS:
        add_box(morphs, x - 0.18 * scale, y - 0.18 * scale, 0.02, 0.36 * scale, 0.36 * scale, 0.22 * scale)
        add_box(morphs, x - 0.55 * scale, y - 0.55 * scale, 0.20, 1.10 * scale, 1.10 * scale, 0.55 * scale)
        add_box(morphs, x - 0.75 * scale, y - 0.10 * scale, 0.46, 1.50 * scale, 0.20 * scale, 0.14 * scale)
        add_box(morphs, x - 0.10 * scale, y - 0.75 * scale, 0.48, 0.20 * scale, 1.50 * scale, 0.14 * scale)

    # Vasi e piccole fioriere lungo portico e percorsi.
    for x, y in POT_POINTS:
        add_box(morphs, x - 0.24, y - 0.24, 0.00, 0.48, 0.48, 0.40)
        add_box(morphs, x - 0.36, y - 0.36, 0.36, 0.72, 0.72, 0.36)

    # Vasca/fontanella sotto il portico, visibile come elemento di corte.
    add_box(morphs, -32.1, 20.0, 0.00, 0.95, 0.95, 0.22)
    add_box(morphs, -31.98, 20.12, 0.22, 0.71, 0.71, 0.18)
    add_box(morphs, -31.78, 20.32, 0.40, 0.31, 0.31, 0.52)
    add_box(morphs, -31.90, 20.20, 0.92, 0.55, 0.55, 0.12)

    # Piccoli sedili/muretti bassi sul bordo corte.
    add_box(morphs, -33.0, 13.9, 0.05, 11.0, 0.22, 0.32)
    add_box(morphs, -33.0, 31.0, 0.05, 11.0, 0.22, 0.32)
    add_box(morphs, -33.0, 13.9, 0.05, 0.22, 17.3, 0.32)
    add_box(morphs, -21.3, 13.9, 0.05, 0.22, 17.3, 0.32)

    return morphs


def build_beams():
    beams = []
    # Bordi dei percorsi/aiuole, per far leggere meglio i limiti delle corti.
    for polygon in LAWN_POLYGONS:
        pts = polygon + [polygon[0]]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            add_beam(beams, x1, y1, x2, y2, 0.08, width=0.065, height=0.045)

    # Percorso pavimentato davanti al portico.
    add_beam(beams, -33.1, 13.85, -20.9, 13.85, 0.10, width=0.09, height=0.05)
    add_beam(beams, -33.1, 31.05, -20.9, 31.05, 0.10, width=0.09, height=0.05)
    add_beam(beams, -32.7, 14.3, -21.2, 30.6, 0.09, width=0.05, height=0.035)
    add_beam(beams, -21.2, 14.3, -32.7, 30.6, 0.09, width=0.05, height=0.035)
    return beams


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "APPLICA":
        print("Crea corte verde, aiuole e piccoli arredi Berra.")
        print("Uso: py 38_tapir_crea_corte_verde_arredi.py APPLICA")
        print("Per rilanciare su layer gia popolato: aggiungere FORZA.")
        return

    force = len(sys.argv) >= 3 and sys.argv[2].upper() == "FORZA"
    conn = ACConnection.connect()
    if not conn:
        raise SystemExit("Connessione Archicad non riuscita.")

    commands = conn.commands
    types = conn.types
    layer_index = create_or_get_layer(commands, types)
    existing = count_elements_on_layer(commands, types, layer_index)
    if existing and not force:
        print(f"Layer {LAYER_NAME} gia popolato con {existing} elementi. Nessuna modifica.")
        print("Usa: py 38_tapir_crea_corte_verde_arredi.py APPLICA FORZA")
        return

    slabs_data = build_lawn_slabs()
    morphs_data = build_morphs()
    beams_data = build_beams()

    slab_result = tapir(commands, types, "CreateSlabs", {"slabsData": slabs_data})
    morph_result = tapir(commands, types, "CreateMorphs", {"morphsData": morphs_data})
    beam_result = tapir(commands, types, "CreateBeams", {"beamsData": beams_data})
    elements = slab_result.get("elements", []) + morph_result.get("elements", []) + beam_result.get("elements", [])
    layer_result = set_elements_layer(commands, types, elements, layer_index)

    OUT_JSON.write_text(
        json.dumps(
            {
                "layer": {"name": LAYER_NAME, "index": layer_index},
                "slabCount": len(slabs_data),
                "morphCount": len(morphs_data),
                "beamCount": len(beams_data),
                "createdCount": len(elements),
                "slabResult": slab_result,
                "morphResult": morph_result,
                "beamResult": beam_result,
                "setLayerResult": layer_result,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Prati/aiuole richiesti: {len(slabs_data)}")
    print(f"Morph arredi/vegetazione richiesti: {len(morphs_data)}")
    print(f"Bordi/percorsi richiesti: {len(beams_data)}")
    print(f"Elementi creati: {len(elements)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
