from __future__ import annotations

import json
import sys
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_portico_loggiato_storico_result.json")
LAYER_NAME = "BERRA_AI_PORTICO_01"


# Linea del loggiato gia impostata dalle colonne della passata 27.
PORTICO_X = -33.08
ARCH_CENTERS_Y = [15.20, 18.00, 20.80, 23.60, 26.40, 29.20]
COLUMN_Y = [13.80, 16.60, 19.40, 22.20, 25.00, 27.80, 30.60]


def tapir(commands, types, name, params=None):
    return commands.ExecuteAddOnCommand(types.AddOnCommandId("TapirCommand", name), params)


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
                    "intersectionGroupNr": 108,
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


def add_arch_ring(morphs, x, y, z=2.35, span=2.25, depth=0.28, thickness=0.18):
    # Ghiera ad arco approssimata a gradoni: coerente con i limiti CreateMorphs.
    bx = x - depth / 2.0
    left = y - span / 2.0
    right = y + span / 2.0
    spring = z
    top = z + 1.08
    pier_w = thickness

    # Spalle dell'arco.
    add_box(morphs, bx, left, 0.55, depth, pier_w, spring - 0.55)
    add_box(morphs, bx, right - pier_w, 0.55, depth, pier_w, spring - 0.55)

    # Archi a gradoni superiori.
    levels = [
        (left + 0.08, right - 0.08, spring + 0.00, 0.18),
        (left + 0.22, right - 0.22, spring + 0.22, 0.18),
        (left + 0.42, right - 0.42, spring + 0.44, 0.18),
        (left + 0.66, right - 0.66, spring + 0.65, 0.18),
        (left + 0.92, right - 0.92, spring + 0.84, 0.20),
    ]
    for y1, y2, zz, hh in levels:
        add_box(morphs, bx, y1, zz, depth, y2 - y1, hh)

    # Sottile bordo interno, per separare luce e muratura.
    add_box(morphs, bx - 0.015, left + 0.26, 0.72, 0.045, 0.10, spring - 0.80)
    add_box(morphs, bx - 0.015, right - 0.36, 0.72, 0.045, 0.10, spring - 0.80)
    add_box(morphs, bx - 0.015, left + 0.48, top - 0.10, 0.045, span - 0.96, 0.10)


def build_morphs():
    morphs = []

    # Basamenti, capitelli e blocchi dei pilastri.
    for y in COLUMN_Y:
        add_box(morphs, PORTICO_X - 0.22, y - 0.24, 0.00, 0.44, 0.48, 0.18)
        add_box(morphs, PORTICO_X - 0.18, y - 0.20, 0.18, 0.36, 0.40, 0.42)
        add_box(morphs, PORTICO_X - 0.24, y - 0.26, 2.36, 0.48, 0.52, 0.18)
        add_box(morphs, PORTICO_X - 0.28, y - 0.30, 2.54, 0.56, 0.60, 0.18)
        add_box(morphs, PORTICO_X - 0.24, y - 0.26, 2.72, 0.48, 0.52, 0.12)

    for y in ARCH_CENTERS_Y:
        add_arch_ring(morphs, PORTICO_X, y)

    # Fascia muraria sopra gli archi, come nella foto del cortile.
    add_box(morphs, PORTICO_X - 0.16, 13.35, 3.02, 0.32, 17.70, 0.36)
    add_box(morphs, PORTICO_X - 0.13, 13.45, 3.44, 0.26, 17.50, 0.18)

    # Ombra/intradosso sotto il portico: leggermente arretrato.
    add_box(morphs, PORTICO_X + 0.18, 13.60, 2.82, 1.35, 17.20, 0.16)

    # Piccoli elementi vegetali davanti al loggiato, coerenti con la corte fotografata.
    plant_points = [(-31.6, 15.0), (-31.3, 20.5), (-31.7, 26.7)]
    for x, y in plant_points:
        add_box(morphs, x - 0.28, y - 0.28, 0.00, 0.56, 0.56, 0.42)
        add_box(morphs, x - 0.62, y - 0.62, 0.38, 1.24, 1.24, 0.82)

    return morphs


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "APPLICA":
        print("Crea portico/loggiato storico Berra.")
        print("Uso: py 35_tapir_crea_portico_loggiato_storico.py APPLICA")
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
        print("Usa: py 35_tapir_crea_portico_loggiato_storico.py APPLICA FORZA")
        return

    morphs_data = build_morphs()
    result = tapir(commands, types, "CreateMorphs", {"morphsData": morphs_data})
    elements = result.get("elements", [])
    layer_result = set_elements_layer(commands, types, elements, layer_index)

    OUT_JSON.write_text(
        json.dumps(
            {
                "layer": {"name": LAYER_NAME, "index": layer_index},
                "morphCount": len(morphs_data),
                "createdCount": len(elements),
                "createResult": result,
                "setLayerResult": layer_result,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Elementi portico richiesti: {len(morphs_data)}")
    print(f"Elementi creati: {len(elements)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
