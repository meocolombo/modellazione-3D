from __future__ import annotations

import json
import sys
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_marcatori_aperture_facce_result.json")
LAYER_NAME = "BERRA_AI_APERTURE_01"


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
                    "intersectionGroupNr": 105,
                }
            ],
            "overwriteExisting": False,
        },
    )
    created = find_layer_index(commands, types, LAYER_NAME)
    if created is None:
        raise RuntimeError(f"Layer non trovato dopo la creazione: {LAYER_NAME}")
    return created


def set_elements_layer(commands, types, elements, layer_index):
    if not elements:
        return None
    return tapir(
        commands,
        types,
        "SetDetailsOfElements",
        {"elementsWithDetails": [{"elementId": e["elementId"], "details": {"layerIndex": layer_index}} for e in elements]},
    )


def add_window_y_facade(morphs, x, y, z, width=1.05, height=1.35, depth=0.08, side="east"):
    # Facciata parallela all'asse Y: apertura come pannello sottile in X.
    bx = x if side == "east" else x - depth
    morphs.append({"basePoint": point3(bx, y - width / 2.0, z), "size": dim3(depth, width, height)})
    morphs.append({"basePoint": point3(bx, y - width / 2.0, z + height + 0.08), "size": dim3(depth, width, 0.12)})


def add_window_x_facade(morphs, x, y, z, width=1.05, height=1.35, depth=0.08, side="north"):
    # Facciata parallela all'asse X: apertura come pannello sottile in Y.
    by = y if side == "north" else y - depth
    morphs.append({"basePoint": point3(x - width / 2.0, by, z), "size": dim3(width, depth, height)})
    morphs.append({"basePoint": point3(x - width / 2.0, by, z + height + 0.08), "size": dim3(width, depth, 0.12)})


def seq(start, stop, step):
    values = []
    v = start
    if start <= stop:
        while v <= stop + 1e-6:
            values.append(round(v, 2))
            v += step
    else:
        while v >= stop - 1e-6:
            values.append(round(v, 2))
            v -= step
    return values


def build_morphs():
    morphs = []
    floor_z = [1.05, 4.10]

    # Fronte lungo ovest e fronte interno lungo: ritmo regolare di finestre.
    for y in seq(-66.0, 27.0, 7.0):
        for z in floor_z:
            add_window_y_facade(morphs, -50.62, y, z, side="west")
            add_window_y_facade(morphs, -41.02, y + 1.6, z, side="east")

    # Fronte est verso strada/corte.
    for y in seq(-68.0, 10.0, 6.5):
        for z in floor_z:
            add_window_y_facade(morphs, -7.78, y, z, width=0.95, side="east")
            add_window_y_facade(morphs, -17.05, y + 0.8, z, width=0.95, side="west")

    # Fronte sud lungo via: finestre e portone centrale.
    for x in seq(-46.0, -11.5, 5.0):
        for z in floor_z:
            add_window_x_facade(morphs, x, -72.22, z, width=0.95, side="south")
    morphs.append({"basePoint": point3(-31.2, -72.28, 0.05), "size": dim3(2.2, 0.10, 2.65)})
    morphs.append({"basePoint": point3(-31.0, -72.34, 2.55), "size": dim3(1.8, 0.12, 0.28)})

    # Corte/loggiato nord: aperture più ravvicinate.
    for x in seq(-32.0, -23.0, 3.0):
        for z in [1.05, 4.05]:
            add_window_x_facade(morphs, x, 13.04, z, width=0.85, side="south")
            add_window_x_facade(morphs, x, 32.95, z, width=0.85, side="north")

    # Corpo centrale sud/nord interno.
    for x in seq(-44.0, -12.0, 5.2):
        for z in floor_z:
            add_window_x_facade(morphs, x, -17.02, z, width=0.95, side="south")
            add_window_x_facade(morphs, x + 0.8, -6.58, z, width=0.95, side="north")

    return morphs


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "APPLICA":
        print("Crea marcatori aperture/facciate per Berra.")
        print("Uso: py 32_tapir_crea_marcatori_aperture_facce.py APPLICA")
        return

    conn = ACConnection.connect()
    if not conn:
        raise SystemExit("Connessione Archicad non riuscita.")

    commands = conn.commands
    types = conn.types
    layer_index = create_or_get_layer(commands, types)
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
    print(f"Marcatori aperture richiesti: {len(morphs_data)}")
    print(f"Elementi creati: {len(elements)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
