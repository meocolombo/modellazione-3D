from __future__ import annotations

import json
import sys
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_fronte_strada_accesso_result.json")
LAYER_NAME = "BERRA_AI_FRONTE_STRADA_01"


def tapir(commands, types, name, params=None):
    return commands.ExecuteAddOnCommand(types.AddOnCommandId("TapirCommand", name), params)


def point3(x, y, z):
    return {"x": float(x), "y": float(y), "z": float(z)}


def dim3(x, y, z):
    return {"x": float(x), "y": float(y), "z": float(z)}


def coord(x, y):
    return {"x": float(x), "y": float(y)}


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
                    "intersectionGroupNr": 109,
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


def add_beam(beams, x1, y1, x2, y2, z, width=0.06, height=0.04):
    beams.append(
        {
            "begCoordinate": coord(x1, y1),
            "endCoordinate": coord(x2, y2),
            "zCoordinate": float(z),
            "width": float(width),
            "height": float(height),
        }
    )


def build_morphs():
    morphs = []

    # Piani urbani: strada in cubetti e marciapiede davanti all'ingresso.
    add_box(morphs, -56.0, -85.0, -0.16, 55.0, 8.3, 0.08)
    add_box(morphs, -56.0, -76.8, -0.10, 55.0, 4.3, 0.07)
    add_box(morphs, -56.0, -72.95, -0.06, 55.0, 0.45, 0.06)

    # Muretto basso e pilastri della cancellata su via Berra.
    add_box(morphs, -50.6, -72.95, 0.00, 17.3, 0.34, 0.82)
    add_box(morphs, -28.4, -72.95, 0.00, 20.1, 0.34, 0.82)
    for x in [-50.6, -42.0, -34.0, -28.2, -20.0, -8.6]:
        add_box(morphs, x - 0.28, -73.08, 0.00, 0.56, 0.58, 2.08)
        add_box(morphs, x - 0.34, -73.14, 2.08, 0.68, 0.70, 0.16)

    # Cancello principale a due ante.
    gate_y = -73.02
    add_box(morphs, -34.05, gate_y, 0.15, 0.16, 0.16, 1.85)
    add_box(morphs, -28.35, gate_y, 0.15, 0.16, 0.16, 1.85)
    add_box(morphs, -34.00, gate_y + 0.02, 1.88, 5.70, 0.10, 0.10)
    add_box(morphs, -34.00, gate_y + 0.02, 0.28, 5.70, 0.10, 0.10)
    for i in range(13):
        x = -33.85 + i * 0.46
        add_box(morphs, x, gate_y - 0.02, 0.28, 0.06, 0.16, 1.60)

    # Recinzione metallica tra pilastri, piu minuta del recinto di base.
    fence_ranges = [(-50.2, -34.5), (-27.8, -8.9)]
    for x1, x2 in fence_ranges:
        add_box(morphs, x1, gate_y + 0.04, 1.65, x2 - x1, 0.08, 0.10)
        add_box(morphs, x1, gate_y + 0.04, 0.72, x2 - x1, 0.08, 0.10)
        count = max(2, int((x2 - x1) / 0.65))
        for i in range(count + 1):
            x = x1 + (x2 - x1) * i / count
            add_box(morphs, x - 0.025, gate_y, 0.75, 0.05, 0.12, 0.95)

    # Lampione urbano e cartelli stradali, letti dalla foto del fronte.
    add_box(morphs, -25.5, -78.7, 0.00, 0.13, 0.13, 4.10)
    add_box(morphs, -25.85, -79.05, 3.85, 0.70, 0.70, 0.28)
    add_box(morphs, -10.5, -76.2, 0.00, 0.08, 0.08, 2.20)
    add_box(morphs, -10.95, -76.25, 1.75, 0.90, 0.08, 0.60)

    # Rastrelliera biciclette a destra dell'ingresso.
    for i in range(6):
        x = -15.8 + i * 0.8
        add_box(morphs, x, -75.6, 0.00, 0.08, 0.65, 0.08)
        add_box(morphs, x, -75.6, 0.08, 0.08, 0.08, 0.70)
        add_box(morphs, x, -75.02, 0.08, 0.08, 0.08, 0.70)
        add_box(morphs, x - 0.02, -75.58, 0.72, 0.12, 0.62, 0.08)

    # Fusto albero su marciapiede e chioma indicativa a sinistra.
    add_box(morphs, -53.6, -76.4, 0.00, 0.30, 0.30, 2.45)
    add_box(morphs, -55.0, -77.8, 2.15, 3.10, 3.10, 3.10)

    return morphs


def build_beams():
    beams = []
    # Giunti della pavimentazione: poche linee, non una griglia pesante.
    for y in [-84.0, -82.6, -81.2, -79.8, -78.4, -77.0]:
        add_beam(beams, -55.5, y, -1.5, y, -0.035, width=0.035, height=0.02)
    for x in [-52, -48, -44, -40, -36, -32, -28, -24, -20, -16, -12, -8, -4]:
        add_beam(beams, x, -84.8, x, -76.9, -0.03, width=0.03, height=0.018)
    add_beam(beams, -55.5, -76.8, -1.5, -76.8, 0.02, width=0.08, height=0.05)
    add_beam(beams, -55.5, -72.65, -1.5, -72.65, 0.04, width=0.08, height=0.05)
    return beams


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "APPLICA":
        print("Crea fronte strada/accesso Berra.")
        print("Uso: py 36_tapir_crea_fronte_strada_accesso.py APPLICA")
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
        print("Usa: py 36_tapir_crea_fronte_strada_accesso.py APPLICA FORZA")
        return

    morphs_data = build_morphs()
    beams_data = build_beams()

    morph_result = tapir(commands, types, "CreateMorphs", {"morphsData": morphs_data})
    beam_result = tapir(commands, types, "CreateBeams", {"beamsData": beams_data})
    elements = morph_result.get("elements", []) + beam_result.get("elements", [])
    layer_result = set_elements_layer(commands, types, elements, layer_index)

    OUT_JSON.write_text(
        json.dumps(
            {
                "layer": {"name": LAYER_NAME, "index": layer_index},
                "morphCount": len(morphs_data),
                "beamCount": len(beams_data),
                "createdCount": len(elements),
                "morphResult": morph_result,
                "beamResult": beam_result,
                "setLayerResult": layer_result,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Morph fronte strada richiesti: {len(morphs_data)}")
    print(f"Travi/giunti richiesti: {len(beams_data)}")
    print(f"Elementi creati: {len(elements)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
