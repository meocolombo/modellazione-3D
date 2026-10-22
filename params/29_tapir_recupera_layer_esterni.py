from __future__ import annotations

import json
import runpy
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_recupero_layer_esterni_result.json")
PASSATA_28 = runpy.run_path(str(Path(__file__).with_name("28_tapir_crea_esterni_corte.py")))
BENCH_POINTS = PASSATA_28["BENCH_POINTS"]
FENCE_LINES = PASSATA_28["FENCE_LINES"]
HEDGE_POINTS = PASSATA_28["HEDGE_POINTS"]
LAYER_NAME = PASSATA_28["LAYER_NAME"]
PAVING_SLABS = PASSATA_28["PAVING_SLABS"]
TREE_POINTS = PASSATA_28["TREE_POINTS"]


def tapir(commands, types, name, params=None):
    return commands.ExecuteAddOnCommand(types.AddOnCommandId("TapirCommand", name), params)


def layer_names(commands, types):
    result = tapir(commands, types, "GetAttributesByType", {"attributeType": "Layer"})
    return {int(item["index"]): item["name"] for item in result.get("attributes", [])}


def find_layer_index(commands, types, layer_name):
    for index, name in layer_names(commands, types).items():
        if name.casefold() == layer_name.casefold():
            return index
    tapir(
        commands,
        types,
        "CreateLayers",
        {
            "layerDataArray": [
                {
                    "name": layer_name,
                    "isHidden": False,
                    "isLocked": False,
                    "isWireframe": False,
                    "intersectionGroupNr": 103,
                }
            ],
            "overwriteExisting": False,
        },
    )
    for index, name in layer_names(commands, types).items():
        if name.casefold() == layer_name.casefold():
            return index
    raise RuntimeError(f"Layer non trovato: {layer_name}")


def bbox(item):
    return item.get("boundingBox3D", {})


def valid_box(box):
    return all(k in box for k in ["xMin", "xMax", "yMin", "yMax", "zMin", "zMax"])


def center(box):
    return ((box["xMin"] + box["xMax"]) / 2.0, (box["yMin"] + box["yMax"]) / 2.0)


def close(a, b, tol):
    return abs(a - b) <= tol


def point_near_targets(x, y, targets, tol=0.35):
    return any(close(x, tx, tol) and close(y, ty, tol) for tx, ty, *_ in targets)


def point_near_shifted_targets(x, y, targets, dx, dy, tolx=0.75, toly=0.75):
    return any(close(x, tx + dx, tolx) and close(y, ty + dy, toly) for tx, ty, *_ in targets)


def slab_matches(box):
    for polygon in PAVING_SLABS:
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        if (
            close(box["xMin"], min(xs), 0.8)
            and close(box["xMax"], max(xs), 0.8)
            and close(box["yMin"], min(ys), 0.8)
            and close(box["yMax"], max(ys), 0.8)
        ):
            return True
    return False


def beam_matches_fence(box):
    if box["zMax"] > 1.45 or box["zMin"] < 0.55:
        return False
    for x1, y1, x2, y2 in FENCE_LINES:
        horizontal = abs(y1 - y2) < 0.01
        vertical = abs(x1 - x2) < 0.01
        if horizontal:
            if close((box["yMin"] + box["yMax"]) / 2.0, y1, 0.35):
                if close(box["xMin"], min(x1, x2), 0.8) and close(box["xMax"], max(x1, x2), 0.8):
                    return True
        if vertical:
            if close((box["xMin"] + box["xMax"]) / 2.0, x1, 0.35):
                if close(box["yMin"], min(y1, y2), 0.8) and close(box["yMax"], max(y1, y2), 0.8):
                    return True
    return False


def column_matches_fence(box):
    if box["zMin"] > 0.15 or box["zMax"] > 3.25:
        return False
    x, y = center(box)
    for x1, y1, x2, y2 in FENCE_LINES:
        horizontal = abs(y1 - y2) < 0.01
        vertical = abs(x1 - x2) < 0.01
        if horizontal and close(y, y1, 0.25) and min(x1, x2) - 0.5 <= x <= max(x1, x2) + 0.5:
            return True
        if vertical and close(x, x1, 0.25) and min(y1, y2) - 0.5 <= y <= max(y1, y2) + 0.5:
            return True
    return False


def object_matches_exterior(box):
    x, y = center(box)
    if point_near_targets(x, y, TREE_POINTS, tol=0.45) and close(box["zMax"], 7.0, 0.2):
        return True
    if point_near_shifted_targets(x, y, HEDGE_POINTS, -0.46, -1.37, tolx=0.8, toly=0.9):
        return True
    if point_near_shifted_targets(x, y, BENCH_POINTS, 0.28, -0.92, tolx=0.6, toly=0.6):
        return True
    return False


def main():
    conn = ACConnection.connect()
    if not conn:
        raise SystemExit("Connessione Archicad non riuscita.")

    commands = conn.commands
    types = conn.types
    layers = layer_names(commands, types)
    target_layer = find_layer_index(commands, types, LAYER_NAME)

    elements = tapir(commands, types, "GetAllElements").get("elements", [])
    details = tapir(commands, types, "GetDetailsOfElements", {"elements": elements}).get("detailsOfElements", [])
    boxes = tapir(commands, types, "Get3DBoundingBoxes", {"elements": elements}).get("boundingBoxes3D", [])

    selected = []
    stats = {}
    for element, detail, box_item in zip(elements, details, boxes):
        box = bbox(box_item)
        if not valid_box(box):
            continue
        type_name = detail.get("type", "")
        layer_name = layers.get(int(detail.get("layerIndex", -1)), "")
        match = False
        if type_name == "Slab" and layer_name == "Strutturale - Portante":
            match = slab_matches(box)
        elif type_name == "Beam" and layer_name == "Strutturale - Portante":
            match = beam_matches_fence(box)
        elif type_name == "Column" and layer_name == "Strutturale - Portante":
            match = column_matches_fence(box)
        elif type_name == "Object" and layer_name == "Interni - Arredo":
            match = object_matches_exterior(box)

        if match:
            selected.append(element)
            stats[type_name] = stats.get(type_name, 0) + 1

    if selected:
        tapir(
            commands,
            types,
            "SetDetailsOfElements",
            {"elementsWithDetails": [{"elementId": e["elementId"], "details": {"layerIndex": target_layer}} for e in selected]},
        )

    OUT_JSON.write_text(
        json.dumps({"layer": {"name": LAYER_NAME, "index": target_layer}, "moved": len(selected), "stats": stats}, indent=2),
        encoding="utf-8",
    )
    print(f"Elementi spostati nel layer {LAYER_NAME}: {len(selected)}")
    for type_name, count in sorted(stats.items()):
        print(f"- {type_name}: {count}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
