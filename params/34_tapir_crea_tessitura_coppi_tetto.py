from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from archicad import ACConnection


OUT_JSON = Path("berra_tessitura_coppi_tetto_result.json")
LAYER_NAME = "BERRA_AI_TEGOLATO_01"


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


def tapir(commands, types, name, params=None):
    return commands.ExecuteAddOnCommand(types.AddOnCommandId("TapirCommand", name), params)


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
                    "intersectionGroupNr": 107,
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
    count = 0
    for detail in details:
        if int(detail.get("layerIndex", -1)) == int(layer_index):
            count += 1
    return count


def set_elements_layer(commands, types, elements, layer_index):
    if not elements:
        return None
    return tapir(
        commands,
        types,
        "SetDetailsOfElements",
        {"elementsWithDetails": [{"elementId": e["elementId"], "details": {"layerIndex": layer_index}} for e in elements]},
    )


def add_beam(beams, x1, y1, x2, y2, z, width=0.055, height=0.035):
    beams.append(
        {
            "begCoordinate": coord(x1, y1),
            "endCoordinate": coord(x2, y2),
            "zCoordinate": float(z),
            "width": float(width),
            "height": float(height),
        }
    )


def build_coppi_beams():
    beams = []
    spacing = 1.10
    for _name, x1, x2, y1, y2, level, angle_deg in ROOF_BLOCKS:
        tan_angle = math.tan(math.radians(angle_deg))
        width_x = abs(x2 - x1)
        width_y = abs(y2 - y1)
        eave_z = level + 0.42
        inset = 0.35

        if width_y >= width_x:
            xm = (x1 + x2) / 2.0
            half = abs(xm - x1)
            steps = max(2, int(half // spacing))
            for i in range(1, steps + 1):
                dist = half * i / (steps + 1)
                z = eave_z + dist * tan_angle
                xl = x1 + dist
                xr = x2 - dist
                add_beam(beams, xl, y1 + inset, xl, y2 - inset, z)
                add_beam(beams, xr, y1 + inset, xr, y2 - inset, z)
        else:
            ym = (y1 + y2) / 2.0
            half = abs(ym - y1)
            steps = max(2, int(half // spacing))
            for i in range(1, steps + 1):
                dist = half * i / (steps + 1)
                z = eave_z + dist * tan_angle
                yl = y1 + dist
                yr = y2 - dist
                add_beam(beams, x1 + inset, yl, x2 - inset, yl, z)
                add_beam(beams, x1 + inset, yr, x2 - inset, yr, z)

        # File di coppi più marcate in prossimità della gronda.
        if width_y >= width_x:
            add_beam(beams, x1 + 0.55, y1 + inset, x1 + 0.55, y2 - inset, eave_z + 0.05, width=0.075, height=0.04)
            add_beam(beams, x2 - 0.55, y1 + inset, x2 - 0.55, y2 - inset, eave_z + 0.05, width=0.075, height=0.04)
        else:
            add_beam(beams, x1 + inset, y1 + 0.55, x2 - inset, y1 + 0.55, eave_z + 0.05, width=0.075, height=0.04)
            add_beam(beams, x1 + inset, y2 - 0.55, x2 - inset, y2 - 0.55, eave_z + 0.05, width=0.075, height=0.04)
    return beams


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "APPLICA":
        print("Crea tessitura semplificata coppi sulle coperture Berra.")
        print("Uso: py 34_tapir_crea_tessitura_coppi_tetto.py APPLICA")
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
        print("Usa: py 34_tapir_crea_tessitura_coppi_tetto.py APPLICA FORZA")
        return

    beams_data = build_coppi_beams()
    try:
        tapir(commands, types, "ApplyFavoritesToElementDefaults", {"favorites": ["Trave generica"]})
    except Exception:
        pass

    result = tapir(commands, types, "CreateBeams", {"beamsData": beams_data})
    elements = result.get("elements", [])
    layer_result = set_elements_layer(commands, types, elements, layer_index)

    OUT_JSON.write_text(
        json.dumps(
            {
                "layer": {"name": LAYER_NAME, "index": layer_index},
                "beamCount": len(beams_data),
                "createdCount": len(elements),
                "createResult": result,
                "setLayerResult": layer_result,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Righe coppi richieste: {len(beams_data)}")
    print(f"Elementi creati: {len(elements)}")
    print(f"Layer: {LAYER_NAME} index {layer_index}")
    print(f"Report: {OUT_JSON}")


if __name__ == "__main__":
    main()
