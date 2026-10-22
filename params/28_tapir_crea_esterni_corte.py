from __future__ import annotations

import json
import sys
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_esterni_corte_result.json")
LAYER_NAME = "BERRA_AI_ESTERNI_01"


TREE_POINTS = [
    (-36.5, -55.0, 4.2), (-31.0, -51.5, 5.0), (-25.2, -48.8, 4.4),
    (-36.8, -40.8, 4.8), (-29.8, -37.2, 5.2), (-23.0, -33.6, 4.6),
    (-38.0, -25.0, 4.2), (-31.5, -22.0, 4.7), (-24.8, -22.8, 4.1),
    (-31.8, -2.2, 4.6), (-26.4, 2.8, 4.0), (-21.8, 8.4, 4.4),
    (-32.0, 19.0, 4.8), (-27.2, 24.7, 4.3), (-22.3, 29.0, 4.1),
]

HEDGE_POINTS = [
    (-40.5, -59.0), (-40.5, -54.0), (-40.5, -49.0), (-40.5, -44.0),
    (-40.5, -39.0), (-40.5, -34.0), (-40.5, -29.0), (-40.5, -24.0),
    (-18.8, -59.0), (-18.8, -54.0), (-18.8, -49.0), (-18.8, -44.0),
    (-18.8, -39.0), (-18.8, -34.0), (-18.8, -29.0), (-18.8, -24.0),
    (-35.0, 14.8), (-30.0, 14.8), (-25.0, 14.8), (-20.0, 14.8),
    (-35.0, 31.0), (-30.0, 31.0), (-25.0, 31.0), (-20.0, 31.0),
]

BENCH_POINTS = [
    (-30.0, -45.0), (-27.0, 21.5), (-35.5, -31.0),
]

LAMP_POINTS = [
    (-12.0, -65.0), (-48.0, -65.0), (-10.0, -8.0), (-42.0, 18.0),
]

PAVING_SLABS = [
    # Corte/giardino sud-ovest.
    [(-39.8, -61.5), (-20.2, -61.5), (-20.2, -22.0), (-39.8, -22.0)],
    # Percorso centrale nel giardino.
    [(-31.5, -61.0), (-28.5, -61.0), (-28.5, -23.0), (-31.5, -23.0)],
    # Corte loggiato/nord.
    [(-34.6, 13.8), (-20.2, 13.8), (-20.2, 31.8), (-34.6, 31.8)],
    # Fascia strada/cancello sud.
    [(-49.6, -72.2), (-8.8, -72.2), (-8.8, -66.0), (-49.6, -66.0)],
]

FENCE_LINES = [
    (-50.2, -72.4, -8.0, -72.4),
    (-50.2, 32.5, -8.0, 32.5),
    (-50.2, -72.4, -50.2, 32.5),
    (-8.0, -72.4, -8.0, 32.5),
    (-42.0, -21.0, -18.0, -21.0),
    (-42.0, -63.5, -18.0, -63.5),
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
                    "intersectionGroupNr": 103,
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
    normalized = []
    for element in elements:
        if "elementId" in element:
            normalized.append(element)
        elif "guid" in element:
            normalized.append({"elementId": {"guid": element["guid"]}})
        else:
            raise KeyError(f"Formato elemento non riconosciuto: {element}")
    return tapir(
        commands,
        types,
        "SetDetailsOfElements",
        {"elementsWithDetails": [{"elementId": e["elementId"], "details": {"layerIndex": layer_index}} for e in normalized]},
    )


def create_objects(commands, types, library_part_name, points, dimensions):
    objects_data = [
        {
            "libraryPartName": library_part_name,
            "coordinates": point3(x, y, 0.0),
            "dimensions": dim3(*dimensions),
        }
        for x, y, *_rest in points
    ]
    return tapir(commands, types, "CreateObjects", {"objectsData": objects_data})


def build_slabs():
    return [
        {
            "level": -0.04,
            "thickness": 0.06,
            "polygonCoordinates": [coord(x, y) for x, y in polygon],
        }
        for polygon in PAVING_SLABS
    ]


def build_fence_beams():
    beams = []
    for x1, y1, x2, y2 in FENCE_LINES:
        for z in [0.75, 1.25]:
            beams.append(
                {
                    "begCoordinate": coord(x1, y1),
                    "endCoordinate": coord(x2, y2),
                    "zCoordinate": z,
                    "width": 0.08,
                    "height": 0.08,
                }
            )
    return beams


def build_fence_posts_morphs():
    posts = []
    for x1, y1, x2, y2 in FENCE_LINES:
        steps = max(2, int(max(abs(x2 - x1), abs(y2 - y1)) // 4))
        for i in range(steps + 1):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            posts.append({"basePoint": point3(x - 0.06, y - 0.06, 0.0), "size": dim3(0.12, 0.12, 1.45)})
    return posts


def fallback_tree_morphs():
    morphs = []
    for x, y, crown in TREE_POINTS:
        morphs.append({"basePoint": point3(x - 0.18, y - 0.18, 0.0), "size": dim3(0.36, 0.36, 2.2)})
        morphs.append({"basePoint": point3(x - crown / 2, y - crown / 2, 2.0), "size": dim3(crown, crown, 2.8)})
    return morphs


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "APPLICA":
        print("Crea passata esterni/corte/verde per Berra.")
        print("Uso: py 28_tapir_crea_esterni_corte.py APPLICA")
        return

    conn = ACConnection.connect()
    if not conn:
        raise SystemExit("Connessione Archicad non riuscita.")
    commands = conn.commands
    types = conn.types
    layer_index = create_or_get_layer(commands, types)

    results = {}
    created = []

    slabs = tapir(commands, types, "CreateSlabs", {"slabsData": build_slabs()})
    results["slabs"] = slabs
    created += slabs.get("elements", [])

    fence_beams = tapir(commands, types, "CreateBeams", {"beamsData": build_fence_beams()})
    results["fenceBeams"] = fence_beams
    created += fence_beams.get("elements", [])

    fence_posts = tapir(commands, types, "CreateMorphs", {"morphsData": build_fence_posts_morphs()})
    results["fencePosts"] = fence_posts
    created += fence_posts.get("elements", [])

    # Oggetti di libreria Archicad. Se un oggetto fallisce, lascio un fallback geometrico.
    try:
        tree_objects = create_objects(commands, types, "Albero Deciduo", TREE_POINTS, (4.0, 4.0, 7.0))
    except Exception as exc:
        tree_objects = {"error": str(exc)}
        tree_fallback = tapir(commands, types, "CreateMorphs", {"morphsData": fallback_tree_morphs()})
        results["treeFallbackMorphs"] = tree_fallback
        created += tree_fallback.get("elements", [])
    else:
        results["trees"] = tree_objects
        created += tree_objects.get("elements", [])

    try:
        hedge_objects = create_objects(commands, types, "Siepe Modello", HEDGE_POINTS, (2.8, 0.7, 1.1))
    except Exception as exc:
        hedge_objects = {"error": str(exc)}
    else:
        created += hedge_objects.get("elements", [])
    results["hedges"] = hedge_objects

    try:
        bench_objects = create_objects(commands, types, "Panchina", BENCH_POINTS, (1.8, 0.7, 0.9))
    except Exception as exc:
        bench_objects = {"error": str(exc)}
    else:
        created += bench_objects.get("elements", [])
    results["benches"] = bench_objects

    try:
        lamp_objects = create_objects(commands, types, "Lampione 01", LAMP_POINTS, (0.6, 0.6, 3.6))
    except Exception as exc:
        lamp_objects = {"error": str(exc)}
    else:
        created += lamp_objects.get("elements", [])
    results["lamps"] = lamp_objects

    layer_result = set_elements_layer(commands, types, created, layer_index)
    output = {
        "layer": {"name": LAYER_NAME, "index": layer_index},
        "createdCount": len(created),
        "setLayerResult": layer_result,
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Elementi esterni/corte creati: {len(created)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
