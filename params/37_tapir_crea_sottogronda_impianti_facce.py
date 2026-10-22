from __future__ import annotations

import json
import sys
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_sottogronda_impianti_facce_result.json")
LAYER_NAME = "BERRA_AI_SOTTOGRONDA_IMPIANTI_01"


ROOF_BLOCKS = [
    ("ala_sud_est", -20.40, -8.20, -72.30, -38.30, 6.30),
    ("ala_sud_ovest", -40.00, -17.00, -63.70, -20.70, 6.30),
    ("corpo_centrale_ovest", -48.80, -43.50, -33.80, -6.60, 6.30),
    ("corpo_centrale_sud", -47.80, -8.00, -17.00, -6.60, 6.30),
    ("corpo_centrale_est", -16.90, -7.70, -39.60, 14.40, 6.30),
    ("corpo_lungo_ovest", -50.80, -41.10, -72.40, 33.10, 6.30),
    ("corpo_nord_centrale", -34.60, -22.10, 13.00, 33.00, 6.30),
    ("corpo_basso_sud_ovest", -41.60, -17.00, -63.80, -21.00, 3.30),
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
                    "intersectionGroupNr": 110,
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


def add_beam(beams, x1, y1, x2, y2, z, width=0.055, height=0.08):
    beams.append(
        {
            "begCoordinate": coord(x1, y1),
            "endCoordinate": coord(x2, y2),
            "zCoordinate": float(z),
            "width": float(width),
            "height": float(height),
        }
    )


def add_box(morphs, x, y, z, sx, sy, sz):
    morphs.append({"basePoint": point3(x, y, z), "size": dim3(sx, sy, sz)})


def build_brackets():
    beams = []
    seen = set()
    for _name, x1, x2, y1, y2, level in ROOF_BLOCKS:
        z = level - 0.18
        # Interasse largo: sottogronda leggibile senza eccesso di geometria.
        interval = 3.0

        # Fronti paralleli a Y: travetti in direzione X.
        for x, sign in [(x1, -1), (x2, 1)]:
            length = max(0.0, abs(y2 - y1))
            count = max(2, int(length // interval))
            for i in range(count + 1):
                y = y1 + length * i / count
                key = (round(x, 1), round(y, 1), "x")
                if key in seen:
                    continue
                seen.add(key)
                add_beam(beams, x, y, x + sign * 0.62, y, z, width=0.06, height=0.10)

        # Fronti paralleli a X: travetti in direzione Y.
        for y, sign in [(y1, -1), (y2, 1)]:
            length = max(0.0, abs(x2 - x1))
            count = max(2, int(length // interval))
            for i in range(count + 1):
                x = x1 + length * i / count
                key = (round(x, 1), round(y, 1), "y")
                if key in seen:
                    continue
                seen.add(key)
                add_beam(beams, x, y, x, y + sign * 0.62, z, width=0.06, height=0.10)
    return beams


def build_pipes_and_cables():
    morphs = []

    # Pluviali e tubazioni corte interne, lettura coerente con foto cortile.
    vertical_pipes = [
        (-33.45, 14.00, 0.20, 5.75), (-33.45, 30.60, 0.20, 5.75),
        (-16.85, -38.60, 0.20, 5.75), (-8.05, -13.20, 0.20, 5.75),
        (-41.25, -62.80, 0.20, 3.10), (-17.10, -62.80, 0.20, 3.10),
        (-50.55, -69.50, 0.20, 5.80), (-8.15, -69.30, 0.20, 5.80),
    ]
    for x, y, z, h in vertical_pipes:
        add_box(morphs, x - 0.045, y - 0.045, z, 0.09, 0.09, h)
        add_box(morphs, x - 0.11, y - 0.11, z + h - 0.15, 0.22, 0.22, 0.12)

    # Linee impiantistiche orizzontali leggere sulle facciate di cortile.
    cable_runs = [
        (-33.55, 13.80, -33.55, 30.80, 2.38),
        (-33.55, 13.80, -33.55, 30.80, 2.55),
        (-41.10, -62.90, -17.00, -62.90, 2.25),
        (-50.55, -69.40, -50.55, -22.00, 2.35),
        (-8.00, -68.80, -8.00, 12.00, 2.40),
    ]
    for x1, y1, x2, y2, z in cable_runs:
        if abs(x1 - x2) < 0.01:
            add_box(morphs, x1 - 0.025, min(y1, y2), z, 0.05, abs(y2 - y1), 0.045)
        else:
            add_box(morphs, min(x1, x2), y1 - 0.025, z, abs(x2 - x1), 0.05, 0.045)

    # Piccole cassette tecniche sui fronti interni.
    boxes = [
        (-33.65, 15.2, 1.45), (-33.65, 27.8, 1.70),
        (-16.95, -32.5, 1.55), (-8.10, -6.5, 1.65),
        (-41.20, -51.5, 1.45), (-50.65, -34.0, 1.50),
    ]
    for x, y, z in boxes:
        add_box(morphs, x - 0.03, y - 0.24, z, 0.08, 0.48, 0.36)

    # Staffe di sostegno pluviali.
    for x, y, z, h in vertical_pipes:
        for dz in [1.0, 2.4, 3.8]:
            if dz < h:
                add_box(morphs, x - 0.14, y - 0.02, z + dz, 0.28, 0.04, 0.045)

    return morphs


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "APPLICA":
        print("Crea sottogronda e impianti facciata Berra.")
        print("Uso: py 37_tapir_crea_sottogronda_impianti_facce.py APPLICA")
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
        print("Usa: py 37_tapir_crea_sottogronda_impianti_facce.py APPLICA FORZA")
        return

    beams_data = build_brackets()
    morphs_data = build_pipes_and_cables()

    beam_result = tapir(commands, types, "CreateBeams", {"beamsData": beams_data})
    morph_result = tapir(commands, types, "CreateMorphs", {"morphsData": morphs_data})
    elements = beam_result.get("elements", []) + morph_result.get("elements", [])
    layer_result = set_elements_layer(commands, types, elements, layer_index)

    OUT_JSON.write_text(
        json.dumps(
            {
                "layer": {"name": LAYER_NAME, "index": layer_index},
                "beamCount": len(beams_data),
                "morphCount": len(morphs_data),
                "createdCount": len(elements),
                "beamResult": beam_result,
                "morphResult": morph_result,
                "setLayerResult": layer_result,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Travetti sottogronda richiesti: {len(beams_data)}")
    print(f"Morph impianti richiesti: {len(morphs_data)}")
    print(f"Elementi creati: {len(elements)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
