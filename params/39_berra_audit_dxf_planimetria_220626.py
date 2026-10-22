from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv


DXF = Path("BERRA PLANIMETRIE PT_P1_COPERTURA_AGGIORNATA_220626.dxf")
OUT_TXT = Path("berra_audit_dxf_planimetria_220626.txt")
OUT_CSV = Path("berra_audit_dxf_planimetria_220626_layers.csv")
OUT_SVG = Path("berra_audit_dxf_planimetria_220626_preview.svg")

X_CODES = {"10", "11", "12", "13"}
Y_CODES = {"20", "21", "22", "23"}

COLORS = [
    "#202020", "#1f77b4", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


def read_groups(path: Path) -> list[tuple[str, str]]:
    raw = path.read_text(encoding="ascii", errors="ignore").splitlines()
    groups = []
    for i in range(0, len(raw) - 1, 2):
        groups.append((raw[i].strip(), raw[i + 1].strip()))
    return groups


def section(groups: list[tuple[str, str]], name: str) -> tuple[int | None, int | None]:
    start = None
    for i in range(len(groups) - 1):
        if groups[i] == ("0", "SECTION") and groups[i + 1] == ("2", name):
            start = i
        elif start is not None and groups[i] == ("0", "ENDSEC"):
            return start, i
    return None, None


def entities(groups: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    s, e = section(groups, "ENTITIES")
    if s is None or e is None:
        return []

    result = []
    current = []

    for code, value in groups[s + 2:e]:
        if code == "0" and value not in {"VERTEX", "SEQEND"} and current:
            result.append(current)
            current = [(code, value)]
        else:
            current.append((code, value))

    if current:
        result.append(current)

    return result


def entity_type(ent: list[tuple[str, str]]) -> str:
    if ent and ent[0][0] == "0":
        return ent[0][1]
    return ""


def layer(ent: list[tuple[str, str]]) -> str:
    for code, value in ent:
        if code == "8":
            return value
    return "0"


def numeric(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def points_from_entity(ent: list[tuple[str, str]]) -> list[tuple[float, float]]:
    pts = []
    pending_x = None

    for code, value in ent:
        if code in X_CODES:
            pending_x = numeric(value)
        elif code in Y_CODES and pending_x is not None:
            y = numeric(value)
            if y is not None:
                pts.append((pending_x, y))
            pending_x = None

    return pts


def bbox_for_entities(ents: list[list[tuple[str, str]]]) -> tuple[float, float, float, float] | None:
    xs = []
    ys = []

    for ent in ents:
        for x, y in points_from_entity(ent):
            xs.append(x)
            ys.append(y)

    if not xs:
        return None

    return min(xs), min(ys), max(xs), max(ys)


def classify_layer(name: str) -> str:
    n = name.casefold()

    if any(k in n for k in ["muro", "mur", "wall", "strutt", "fabbr", "edificio", "building", "portante"]):
        return "fabbricato/struttura"

    if any(k in n for k in ["verde", "aiuol", "alber", "tree", "garden", "prato", "corte", "giardino"]):
        return "verde/corte"

    if any(k in n for k in ["roof", "copert", "falda", "tetto"]):
        return "coperture"

    if any(k in n for k in ["quota", "test", "text", "dim", "note"]):
        return "quote/testi"

    if any(k in n for k in ["confine", "lotto", "perimetro", "boundary"]):
        return "confine/lotto"

    if any(k in n for k in ["strada", "via", "road", "marciapiede"]):
        return "strada/contesto"

    return "da verificare"


def layer_stats(ents: list[list[tuple[str, str]]]):
    by_layer = defaultdict(list)

    for ent in ents:
        by_layer[layer(ent)].append(ent)

    rows = []

    for layer_name, layer_ents in sorted(by_layer.items()):
        type_counter = Counter(entity_type(e) for e in layer_ents)
        box = bbox_for_entities(layer_ents)
        rows.append(
            {
                "layer": layer_name,
                "classificazione": classify_layer(layer_name),
                "entities": len(layer_ents),
                "types": "; ".join(f"{k}:{v}" for k, v in sorted(type_counter.items())),
                "bbox": box,
            }
        )

    return rows


def color_for_layer(layer_name: str, index: int) -> str:
    cls = classify_layer(layer_name)

    if cls == "fabbricato/struttura":
        return "#222222"
    if cls == "verde/corte":
        return "#228B3B"
    if cls == "coperture":
        return "#7B3FB2"
    if cls == "quote/testi":
        return "#b77b00"
    if cls == "confine/lotto":
        return "#1b55aa"
    if cls == "strada/contesto":
        return "#999999"

    return COLORS[index % len(COLORS)]


def write_svg(ents: list[list[tuple[str, str]]], rows: list[dict]):
    box = bbox_for_entities(ents)
    if not box:
        OUT_SVG.write_text("<svg></svg>", encoding="utf-8")
        return

    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0

    layer_index = {row["layer"]: i for i, row in enumerate(rows)}

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.3f} {-y1:.3f} {w:.3f} {h:.3f}" width="1200" height="900">'
    )
    out.append('<rect x="-100000" y="-100000" width="200000" height="200000" fill="white"/>')

    for ent in ents:
        typ = entity_type(ent)
        lay = layer(ent)
        col = color_for_layer(lay, layer_index.get(lay, 0))
        pts = points_from_entity(ent)

        if typ == "LINE" and len(pts) >= 2:
            (x_a, y_a), (x_b, y_b) = pts[0], pts[1]
            out.append(
                f'<line x1="{x_a:.3f}" y1="{-y_a:.3f}" x2="{x_b:.3f}" y2="{-y_b:.3f}" '
                f'stroke="{col}" stroke-width="0.12" fill="none" opacity="0.88"/>'
            )

        elif typ in {"LWPOLYLINE", "POLYLINE"} and len(pts) >= 2:
            poly_pts = " ".join(f"{x:.3f},{-y:.3f}" for x, y in pts)
            out.append(
                f'<polyline points="{poly_pts}" stroke="{col}" stroke-width="0.13" fill="none" opacity="0.88"/>'
            )

        elif typ == "CIRCLE" and pts:
            r = None
            for code, value in ent:
                if code == "40":
                    r = numeric(value)
                    break

            if r:
                x, y = pts[0]
                out.append(
                    f'<circle cx="{x:.3f}" cy="{-y:.3f}" r="{r:.3f}" '
                    f'stroke="{col}" stroke-width="0.12" fill="none" opacity="0.75"/>'
                )

    out.append("</svg>")
    OUT_SVG.write_text("\n".join(out), encoding="utf-8")


def main():
    if not DXF.exists():
        raise FileNotFoundError(f"DXF non trovato: {DXF.resolve()}")

    groups = read_groups(DXF)
    ents = entities(groups)
    rows = layer_stats(ents)
    global_box = bbox_for_entities(ents)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["layer", "classificazione", "entities", "types", "bbox"])

        for row in rows:
            writer.writerow(
                [
                    row["layer"],
                    row["classificazione"],
                    row["entities"],
                    row["types"],
                    row["bbox"],
                ]
            )

    report = []
    report.append("AUDIT DXF PLANIMETRIA BERRA 220626")
    report.append("=" * 44)
    report.append(f"File: {DXF.resolve()}")
    report.append(f"Entita totali: {len(ents)}")
    report.append(f"Layer totali: {len(rows)}")
    report.append(f"BBox globale: {global_box}")

    if global_box:
        x0, y0, x1, y1 = global_box
        report.append(f"Dimensione bbox: {x1 - x0:.3f} x {y1 - y0:.3f}")

    report.append("")
    report.append("Layer:")

    for row in rows:
        report.append(
            f"- {row['layer']}: {row['entities']} entita; "
            f"{row['classificazione']}; {row['types']}; bbox={row['bbox']}"
        )

    report.append("")
    report.append("Note operative:")
    report.append("- Usare i layer fabbricato/struttura per verificare l'allineamento con il modello Archicad.")
    report.append("- Usare i layer verde/corte per correggere BERRA_AI_CORTE_VERDE_01 con una nuova passata.")
    report.append("- Usare i layer strada/contesto per separare via Berra dal modello edificio.")
    report.append("- Ignorare inizialmente quote/testi per la generazione 3D.")

    OUT_TXT.write_text("\n".join(report) + "\n", encoding="utf-8")
    write_svg(ents, rows)

    print("Audit generato:")
    print(OUT_TXT.resolve())
    print(OUT_CSV.resolve())
    print(OUT_SVG.resolve())


if __name__ == "__main__":
    main()