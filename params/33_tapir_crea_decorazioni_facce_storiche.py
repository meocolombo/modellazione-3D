from __future__ import annotations

import json
import sys
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_decorazioni_facce_storiche_result.json")
LAYER_NAME = "BERRA_AI_DECORAZIONI_01"


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
                    "intersectionGroupNr": 106,
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


def add_x_facade_lancet(morphs, x, y, z, width=1.05, height=1.95, depth=0.075, side="east"):
    bx = x if side == "east" else x - depth
    strip = 0.14
    # Spalle e davanzale.
    morphs.append({"basePoint": point3(bx, y - width / 2, z), "size": dim3(depth, strip, height)})
    morphs.append({"basePoint": point3(bx, y + width / 2 - strip, z), "size": dim3(depth, strip, height)})
    morphs.append({"basePoint": point3(bx, y - width / 2 - 0.10, z - 0.13), "size": dim3(depth, width + 0.20, 0.13)})
    # Arco ogivale semplificato a gradoni.
    morphs.append({"basePoint": point3(bx, y - width * 0.42, z + height - 0.10), "size": dim3(depth, width * 0.84, 0.14)})
    morphs.append({"basePoint": point3(bx, y - width * 0.30, z + height + 0.08), "size": dim3(depth, width * 0.60, 0.15)})
    morphs.append({"basePoint": point3(bx, y - width * 0.16, z + height + 0.26), "size": dim3(depth, width * 0.32, 0.17)})


def add_y_facade_lancet(morphs, x, y, z, width=1.05, height=1.95, depth=0.075, side="south"):
    by = y if side == "north" else y - depth
    strip = 0.14
    morphs.append({"basePoint": point3(x - width / 2, by, z), "size": dim3(strip, depth, height)})
    morphs.append({"basePoint": point3(x + width / 2 - strip, by, z), "size": dim3(strip, depth, height)})
    morphs.append({"basePoint": point3(x - width / 2 - 0.10, by, z - 0.13), "size": dim3(width + 0.20, depth, 0.13)})
    morphs.append({"basePoint": point3(x - width * 0.42, by, z + height - 0.10), "size": dim3(width * 0.84, depth, 0.14)})
    morphs.append({"basePoint": point3(x - width * 0.30, by, z + height + 0.08), "size": dim3(width * 0.60, depth, 0.15)})
    morphs.append({"basePoint": point3(x - width * 0.16, by, z + height + 0.26), "size": dim3(width * 0.32, depth, 0.17)})


def add_x_facade_oculus(morphs, x, y, z, radius=0.42, depth=0.075, side="east"):
    bx = x if side == "east" else x - depth
    # Anello circolare approssimato con otto tasselli ortogonali.
    r = radius
    t = 0.12
    morphs.append({"basePoint": point3(bx, y - r, z + r - t / 2), "size": dim3(depth, 2 * r, t)})
    morphs.append({"basePoint": point3(bx, y - r, z - r + t / 2), "size": dim3(depth, 2 * r, t)})
    morphs.append({"basePoint": point3(bx, y - r + t / 2, z - r), "size": dim3(depth, t, 2 * r)})
    morphs.append({"basePoint": point3(bx, y + r - t * 1.5, z - r), "size": dim3(depth, t, 2 * r)})
    morphs.append({"basePoint": point3(bx, y - r * 0.70, z + r * 0.62), "size": dim3(depth, r * 0.55, t)})
    morphs.append({"basePoint": point3(bx, y + r * 0.15, z + r * 0.62), "size": dim3(depth, r * 0.55, t)})
    morphs.append({"basePoint": point3(bx, y - r * 0.70, z - r * 0.72), "size": dim3(depth, r * 0.55, t)})
    morphs.append({"basePoint": point3(bx, y + r * 0.15, z - r * 0.72), "size": dim3(depth, r * 0.55, t)})


def add_y_facade_oculus(morphs, x, y, z, radius=0.42, depth=0.075, side="south"):
    by = y if side == "north" else y - depth
    r = radius
    t = 0.12
    morphs.append({"basePoint": point3(x - r, by, z + r - t / 2), "size": dim3(2 * r, depth, t)})
    morphs.append({"basePoint": point3(x - r, by, z - r + t / 2), "size": dim3(2 * r, depth, t)})
    morphs.append({"basePoint": point3(x - r + t / 2, by, z - r), "size": dim3(t, depth, 2 * r)})
    morphs.append({"basePoint": point3(x + r - t * 1.5, by, z - r), "size": dim3(t, depth, 2 * r)})
    morphs.append({"basePoint": point3(x - r * 0.70, by, z + r * 0.62), "size": dim3(r * 0.55, depth, t)})
    morphs.append({"basePoint": point3(x + r * 0.15, by, z + r * 0.62), "size": dim3(r * 0.55, depth, t)})
    morphs.append({"basePoint": point3(x - r * 0.70, by, z - r * 0.72), "size": dim3(r * 0.55, depth, t)})
    morphs.append({"basePoint": point3(x + r * 0.15, by, z - r * 0.72), "size": dim3(r * 0.55, depth, t)})


def add_x_facade_quoins(morphs, x, y, side="east", zmax=6.4):
    bx = x if side == "east" else x - 0.08
    z = 0.35
    toggle = False
    while z < zmax:
        length = 0.42 if toggle else 0.30
        morphs.append({"basePoint": point3(bx, y - length / 2, z), "size": dim3(0.08, length, 0.32)})
        z += 0.55
        toggle = not toggle


def add_y_facade_quoins(morphs, x, y, side="south", zmax=6.4):
    by = y if side == "north" else y - 0.08
    z = 0.35
    toggle = False
    while z < zmax:
        length = 0.42 if toggle else 0.30
        morphs.append({"basePoint": point3(x - length / 2, by, z), "size": dim3(length, 0.08, 0.32)})
        z += 0.55
        toggle = not toggle


def build_morphs():
    morphs = []

    # Facciata storica laterale ripresa dal render Lumion: ritmo ogivale e oculi.
    for y in [-11.0, -6.0, -1.0, 4.0, 9.0, 13.0]:
        add_x_facade_lancet(morphs, -7.64, y, 0.90, width=1.00, side="east")
        add_x_facade_lancet(morphs, -7.64, y, 3.65, width=1.00, side="east")
        add_x_facade_oculus(morphs, -7.63, y, 6.15, radius=0.36, side="east")

    # Fronte su strada con portale e aperture ad arco.
    for x in [-45.0, -39.5, -34.0, -24.5, -19.0, -13.5]:
        add_y_facade_lancet(morphs, x, -72.16, 0.90, width=1.00, side="south")
        add_y_facade_lancet(morphs, x, -72.16, 3.65, width=1.00, side="south")
        add_y_facade_oculus(morphs, x, -72.17, 6.15, radius=0.35, side="south")

    # Apertura principale/portale.
    add_y_facade_lancet(morphs, -30.5, -72.15, 0.25, width=1.65, height=2.65, side="south")
    add_y_facade_oculus(morphs, -30.5, -72.17, 5.95, radius=0.42, side="south")

    # Cantonali chiari sugli spigoli più visibili.
    for y in [-13.8, 14.6]:
        add_x_facade_quoins(morphs, -7.60, y, side="east", zmax=6.8)
    for x in [-50.8, -41.1, -20.4, -8.2]:
        add_y_facade_quoins(morphs, x, -72.35, side="south", zmax=6.8)

    # Cornicione alto bianco sotto gronda sui fronti decorati.
    morphs.append({"basePoint": point3(-7.62, -13.8, 6.75), "size": dim3(0.08, 28.4, 0.18)})
    morphs.append({"basePoint": point3(-47.5, -72.24, 6.75), "size": dim3(39.0, 0.08, 0.18)})
    return morphs


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "APPLICA":
        print("Crea decorazioni facciate storiche Berra.")
        print("Uso: py 33_tapir_crea_decorazioni_facce_storiche.py APPLICA")
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

    print(f"Decorazioni facciata richieste: {len(morphs_data)}")
    print(f"Elementi creati: {len(elements)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
