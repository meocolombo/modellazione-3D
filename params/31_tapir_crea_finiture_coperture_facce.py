from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_finiture_coperture_facce_result.json")
LAYER_NAME = "BERRA_AI_FINITURE_01"


ROOF_BLOCKS = [
    ("ala_sud_est", -20.40, -8.20, -72.30, -38.30, 6.30, 30.0),
    ("ala_sud_ovest", -40.00, -17.00, -63.70, -20.70, 6.30, 30.0),
    ("corpo_centrale_ovest", -48.80, -43.50, -33.80, -6.60, 6.30, 30.0),
    ("corpo_centrale_sud", -47.80, -8.00, -17.00, -6.60, 6.30, 30.0),
    ("corpo_centrale_est", -16.90, -7.70, -39.60, 14.40, 6.30, 30.0),
    ("corpo_nord_ovest", -39.20, -25.40, 8.20, 14.50, 6.30, 30.0),
    ("corpo_lungo_ovest", -50.80, -41.10, -72.40, 33.10, 6.30, 28.0),
    ("corpo_nord_centrale", -34.60, -22.10, 13.00, 33.00, 6.30, 30.0),
    ("corpo_nord_est", -23.40, -9.00, 7.80, 14.50, 6.30, 30.0),
    ("corpo_est_corto", -10.20, -7.70, -13.80, 14.60, 6.30, 28.0),
    ("corpo_ovest_corte", -39.40, -35.70, -8.20, 6.30, 6.30, 28.0),
    ("corpo_basso_sud_ovest", -41.60, -17.00, -63.80, -21.00, 3.30, 24.0),
]

COURTYARD_ARCADE_MARKERS = [
    (-33.15, 14.2, 3.15), (-33.15, 17.0, 3.15), (-33.15, 19.8, 3.15),
    (-33.15, 22.6, 3.15), (-33.15, 25.4, 3.15), (-33.15, 28.2, 3.15),
    (-33.15, 30.9, 3.15),
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
                    "intersectionGroupNr": 104,
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


def add_beam(beams, x1, y1, x2, y2, z, width, height):
    beams.append(
        {
            "begCoordinate": coord(x1, y1),
            "endCoordinate": coord(x2, y2),
            "zCoordinate": float(z),
            "width": float(width),
            "height": float(height),
        }
    )


def build_roof_finish_beams():
    beams = []
    seen_edges = set()
    for _name, x1, x2, y1, y2, level, angle_deg in ROOF_BLOCKS:
        width_x = abs(x2 - x1)
        width_y = abs(y2 - y1)
        ridge_raise = min(width_x, width_y) * 0.5 * math.tan(math.radians(angle_deg))
        ridge_z = level + 0.34 + ridge_raise
        eave_z = level + 0.18

        # Colmo principale, più sottile delle capriate.
        if width_y >= width_x:
            xm = (x1 + x2) / 2.0
            add_beam(beams, xm, y1 - 0.20, xm, y2 + 0.20, ridge_z, 0.10, 0.12)
        else:
            ym = (y1 + y2) / 2.0
            add_beam(beams, x1 - 0.20, ym, x2 + 0.20, ym, ridge_z, 0.10, 0.12)

        # Gonde/cornici sui quattro lati, deduplicate sui blocchi sovrapposti.
        edges = [
            (x1 - 0.20, y1 - 0.20, x2 + 0.20, y1 - 0.20),
            (x1 - 0.20, y2 + 0.20, x2 + 0.20, y2 + 0.20),
            (x1 - 0.20, y1 - 0.20, x1 - 0.20, y2 + 0.20),
            (x2 + 0.20, y1 - 0.20, x2 + 0.20, y2 + 0.20),
        ]
        for edge in edges:
            key = tuple(round(v, 2) for v in edge)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            add_beam(beams, *edge, eave_z, 0.09, 0.10)
    return beams


def build_downspouts():
    points = {}
    for _name, x1, x2, y1, y2, level, _angle in ROOF_BLOCKS:
        height = max(3.0, level + 0.15)
        for x, y in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
            key = (round(x, 1), round(y, 1))
            points[key] = max(points.get(key, 0.0), height)
    morphs = []
    for (x, y), height in sorted(points.items()):
        morphs.append({"basePoint": point3(x - 0.045, y - 0.045, 0.0), "size": dim3(0.09, 0.09, height)})
    return morphs


def build_facade_markers():
    morphs = []
    # Archi/loggiato: piccoli architravi e fasce che rendono leggibile il fronte porticato.
    for x, y, z in COURTYARD_ARCADE_MARKERS:
        morphs.append({"basePoint": point3(x - 0.18, y - 0.90, z), "size": dim3(0.20, 1.80, 0.16)})
        morphs.append({"basePoint": point3(x - 0.18, y - 0.70, z + 2.75), "size": dim3(0.20, 1.40, 0.14)})
    # Fasce orizzontali leggere sui fronti lunghi.
    long_bands = [
        (-50.75, -71.8, -50.75, 32.8, 3.05),
        (-41.15, -71.8, -41.15, 32.8, 3.05),
        (-8.05, -71.6, -8.05, 14.0, 3.05),
        (-17.05, -63.4, -17.05, -20.9, 3.05),
    ]
    for x1, y1, x2, y2, z in long_bands:
        if abs(x1 - x2) < 0.01:
            morphs.append({"basePoint": point3(x1 - 0.05, min(y1, y2), z), "size": dim3(0.10, abs(y2 - y1), 0.12)})
            morphs.append({"basePoint": point3(x1 - 0.05, min(y1, y2), z + 2.80), "size": dim3(0.10, abs(y2 - y1), 0.12)})
        else:
            morphs.append({"basePoint": point3(min(x1, x2), y1 - 0.05, z), "size": dim3(abs(x2 - x1), 0.10, 0.12)})
            morphs.append({"basePoint": point3(min(x1, x2), y1 - 0.05, z + 2.80), "size": dim3(abs(x2 - x1), 0.10, 0.12)})
    return morphs


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "APPLICA":
        print("Crea finiture coperture/facciate per Berra.")
        print("Uso: py 31_tapir_crea_finiture_coperture_facce.py APPLICA")
        return

    conn = ACConnection.connect()
    if not conn:
        raise SystemExit("Connessione Archicad non riuscita.")

    commands = conn.commands
    types = conn.types
    layer_index = create_or_get_layer(commands, types)

    beams_data = build_roof_finish_beams()
    morphs_data = build_downspouts() + build_facade_markers()

    beam_result = tapir(commands, types, "CreateBeams", {"beamsData": beams_data})
    morph_result = tapir(commands, types, "CreateMorphs", {"morphsData": morphs_data})
    elements = beam_result.get("elements", []) + morph_result.get("elements", [])
    layer_result = set_elements_layer(commands, types, elements, layer_index)

    output = {
        "layer": {"name": LAYER_NAME, "index": layer_index},
        "beamCount": len(beams_data),
        "morphCount": len(morphs_data),
        "createdCount": len(elements),
        "beamResult": beam_result,
        "morphResult": morph_result,
        "setLayerResult": layer_result,
    }
    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Travi finitura richieste: {len(beams_data)}")
    print(f"Morph finitura richiesti: {len(morphs_data)}")
    print(f"Elementi creati: {len(elements)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
