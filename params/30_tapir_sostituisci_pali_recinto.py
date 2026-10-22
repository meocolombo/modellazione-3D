from __future__ import annotations

import json
import runpy
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_sostituzione_pali_recinto_result.json")
PASSATA_28 = runpy.run_path(str(Path(__file__).with_name("28_tapir_crea_esterni_corte.py")))
FENCE_LINES = PASSATA_28["FENCE_LINES"]
LAYER_NAME = PASSATA_28["LAYER_NAME"]
LAMP_POINTS = PASSATA_28["LAMP_POINTS"]


def tapir(commands, types, name, params=None):
    return commands.ExecuteAddOnCommand(types.AddOnCommandId("TapirCommand", name), params)


def point3(x, y, z):
    return {"x": float(x), "y": float(y), "z": float(z)}


def dim3(x, y, z):
    return {"x": float(x), "y": float(y), "z": float(z)}


def layer_names(commands, types):
    result = tapir(commands, types, "GetAttributesByType", {"attributeType": "Layer"})
    return {int(item["index"]): item["name"] for item in result.get("attributes", [])}


def target_layer_index(commands, types):
    for index, name in layer_names(commands, types).items():
        if name.casefold() == LAYER_NAME.casefold():
            return index
    raise RuntimeError(f"Layer non trovato: {LAYER_NAME}")


def set_elements_layer(commands, types, elements, layer_index):
    if not elements:
        return None
    return tapir(
        commands,
        types,
        "SetDetailsOfElements",
        {"elementsWithDetails": [{"elementId": e["elementId"], "details": {"layerIndex": layer_index}} for e in elements]},
    )


def build_post_morphs():
    morphs = []
    for x1, y1, x2, y2 in FENCE_LINES:
        steps = max(2, int(max(abs(x2 - x1), abs(y2 - y1)) // 4))
        for i in range(steps + 1):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            morphs.append({"basePoint": point3(x - 0.06, y - 0.06, 0.0), "size": dim3(0.12, 0.12, 1.45)})
    return morphs


def build_lamp_morphs():
    morphs = []
    for x, y in LAMP_POINTS:
        morphs.append({"basePoint": point3(x - 0.05, y - 0.05, 0.0), "size": dim3(0.10, 0.10, 3.20)})
        morphs.append({"basePoint": point3(x - 0.28, y - 0.28, 3.05), "size": dim3(0.56, 0.56, 0.22)})
    return morphs


def main():
    conn = ACConnection.connect()
    if not conn:
        raise SystemExit("Connessione Archicad non riuscita.")

    commands = conn.commands
    types = conn.types
    layers = layer_names(commands, types)
    layer_index = target_layer_index(commands, types)

    elements = tapir(commands, types, "GetAllElements").get("elements", [])
    details = tapir(commands, types, "GetDetailsOfElements", {"elements": elements}).get("detailsOfElements", [])

    columns_to_delete = []
    for element, detail in zip(elements, details):
        layer_name = layers.get(int(detail.get("layerIndex", -1)), "")
        if detail.get("type") == "Column" and layer_name.casefold() == LAYER_NAME.casefold():
            columns_to_delete.append(element)

    delete_result = None
    if columns_to_delete:
        delete_result = tapir(commands, types, "DeleteElements", {"elements": columns_to_delete})

    morphs_data = build_post_morphs() + build_lamp_morphs()
    morph_result = tapir(commands, types, "CreateMorphs", {"morphsData": morphs_data})
    created = morph_result.get("elements", [])
    set_layer_result = set_elements_layer(commands, types, created, layer_index)

    OUT_JSON.write_text(
        json.dumps(
            {
                "layer": {"name": LAYER_NAME, "index": layer_index},
                "deletedColumns": len(columns_to_delete),
                "deleteResult": delete_result,
                "createdMorphs": len(created),
                "setLayerResult": set_layer_result,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Colonne recinzione eliminate dal layer AI: {len(columns_to_delete)}")
    print(f"Morph pali/lampioni creati: {len(created)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
