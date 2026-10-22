from __future__ import annotations

from pathlib import Path
from collections import Counter


DXF = Path("BERRA PLANIMETRIE PT_P1_COPERTURA_AGGIORNATA_220626.dxf")

OUT_SVG = Path("berra_pianta_centrale_isolata.svg")
OUT_TXT = Path("berra_pianta_centrale_isolata_report.txt")
OUT_DXF = Path("berra_pianta_centrale_isolata.dxf")

X_CODES = {"10", "11", "12", "13"}
Y_CODES = {"20", "21", "22", "23"}

# Primo tentativo di ritaglio: esclude sezioni/prospetti capriate sopra e sotto.
X_MIN_PIANTA = 3000
X_MAX_PIANTA = 7800
Y_MIN_PIANTA = 3800
Y_MAX_PIANTA = 13200

KEEP_LAYERS = {
    "00_STRUTTURE MURI",
    "MURATURE",
    "B_COPERTURA",
    "B_TRAVI",
    "METALLI",
    "B_ASSITI",
    "B_VISTE",
}

# Escludo CAPRIATE_LEGNO e C_MENSOLE dal primo taglio planimetrico
# perché possono appartenere ai prospetti/sezioni delle capriate.
SKIP_LAYERS = {
    "CAPRIATE_LEGNO",
    "C_MENSOLE",
}

SKIP_TYPES = {
    "TEXT",
    "MTEXT",
    "DIMENSION",
    "MULTILEADER",
    "HATCH",
}

COLORS = {
    "00_STRUTTURE MURI": "#111111",
    "MURATURE": "#444444",
    "B_COPERTURA": "#7B3FB2",
    "B_TRAVI": "#9a6a2f",
    "METALLI": "#517a9b",
    "B_ASSITI": "#6f4e37",
    "B_VISTE": "#999999",
}

DXF_LAYER_COLORS = {
    "PIANTA_00_STRUTTURE_MURI": 7,
    "PIANTA_MURATURE": 8,
    "PIANTA_B_COPERTURA": 6,
    "PIANTA_B_TRAVI": 30,
    "PIANTA_METALLI": 5,
    "PIANTA_B_ASSITI": 34,
    "PIANTA_B_VISTE": 9,
    "RITAGLIO_PIANTA": 1,
}


def read_groups(path: Path) -> list[tuple[str, str]]:
    raw = path.read_text(encoding="ascii", errors="ignore").splitlines()
    return [(raw[i].strip(), raw[i + 1].strip()) for i in range(0, len(raw) - 1, 2)]


def write_groups(path: Path, groups: list[tuple[str, str]]) -> None:
    flat = []
    for code, value in groups:
        flat.append(str(code))
        flat.append(str(value))
    path.write_text("\n".join(flat) + "\n", encoding="ascii")


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


def bbox(ents: list[list[tuple[str, str]]]) -> tuple[float, float, float, float] | None:
    xs = []
    ys = []

    for ent in ents:
        for x, y in points_from_entity(ent):
            xs.append(x)
            ys.append(y)

    if not xs:
        return None

    return min(xs), min(ys), max(xs), max(ys)


def entity_inside_crop(ent: list[tuple[str, str]]) -> bool:
    pts = points_from_entity(ent)
    if not pts:
        return False

    # Uso centroide semplice dei punti dell'entità.
    cx = sum(x for x, _ in pts) / len(pts)
    cy = sum(y for _, y in pts) / len(pts)

    return (
        X_MIN_PIANTA <= cx <= X_MAX_PIANTA
        and Y_MIN_PIANTA <= cy <= Y_MAX_PIANTA
    )


def is_plan_entity(ent: list[tuple[str, str]]) -> bool:
    typ = entity_type(ent)
    lay = layer(ent)

    if typ in SKIP_TYPES:
        return False

    if lay in SKIP_LAYERS:
        return False

    if lay not in KEEP_LAYERS:
        return False

    if not entity_inside_crop(ent):
        return False

    return True


def set_layer(ent: list[tuple[str, str]], new_layer: str) -> list[tuple[str, str]]:
    out = []
    done = False

    for code, value in ent:
        if code == "8" and not done:
            out.append((code, new_layer))
            done = True
        else:
            out.append((code, value))

    if not done:
        out.insert(1, ("8", new_layer))

    return out


def layer_table() -> list[tuple[str, str]]:
    out = [
        ("0", "TABLE"),
        ("2", "LAYER"),
        ("70", str(len(DXF_LAYER_COLORS))),
    ]

    for name, color in DXF_LAYER_COLORS.items():
        out += [
            ("0", "LAYER"),
            ("2", name),
            ("70", "0"),
            ("62", str(color)),
            ("6", "CONTINUOUS"),
        ]

    out += [("0", "ENDTAB")]
    return out


def dxf_line(layer_name: str, x1: float, y1: float, x2: float, y2: float) -> list[tuple[str, str]]:
    return [
        ("0", "LINE"),
        ("8", layer_name),
        ("10", f"{x1:.3f}"),
        ("20", f"{y1:.3f}"),
        ("30", "0"),
        ("11", f"{x2:.3f}"),
        ("21", f"{y2:.3f}"),
        ("31", "0"),
    ]


def crop_frame_entities() -> list[list[tuple[str, str]]]:
    pts = [
        (X_MIN_PIANTA, Y_MIN_PIANTA),
        (X_MAX_PIANTA, Y_MIN_PIANTA),
        (X_MAX_PIANTA, Y_MAX_PIANTA),
        (X_MIN_PIANTA, Y_MAX_PIANTA),
    ]
    return [
        dxf_line("RITAGLIO_PIANTA", a[0], a[1], b[0], b[1])
        for a, b in zip(pts, pts[1:] + pts[:1])
    ]


def make_dxf(plan_ents: list[list[tuple[str, str]]]) -> list[tuple[str, str]]:
    out = []
    out += [
        ("0", "SECTION"),
        ("2", "HEADER"),
        ("9", "$ACADVER"),
        ("1", "AC1009"),
        ("0", "ENDSEC"),
    ]

    out += [
        ("0", "SECTION"),
        ("2", "TABLES"),
    ]

    out += layer_table()

    out += [
        ("0", "ENDSEC"),
        ("0", "SECTION"),
        ("2", "ENTITIES"),
    ]

    for ent in plan_ents:
        new_layer = "PIANTA_" + layer(ent).replace(" ", "_").replace("-", "_")
        out += set_layer(ent, new_layer)

    for ent in crop_frame_entities():
        out += ent

    out += [
        ("0", "ENDSEC"),
        ("0", "EOF"),
    ]

    return out


def write_svg(plan_ents: list[list[tuple[str, str]]]) -> None:
    all_ents = plan_ents + crop_frame_entities()
    box = bbox(all_ents)

    if box is None:
        OUT_SVG.write_text("<svg></svg>", encoding="utf-8")
        return

    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0

    canvas_w = 1200
    canvas_h = 1800
    margin = 80

    scale = min((canvas_w - 2 * margin) / w, (canvas_h - 2 * margin) / h)

    def sx(x: float) -> float:
        return margin + (x - x0) * scale

    def sy(y: float) -> float:
        return canvas_h - margin - (y - y0) * scale

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}">'
    )
    out.append('<rect width="100%" height="100%" fill="#fbfbfb"/>')

    # Griglia
    grid_step = 500
    gx = int(x0 // grid_step) * grid_step
    while gx <= x1:
        xx = sx(gx)
        out.append(f'<line x1="{xx:.2f}" y1="{margin}" x2="{xx:.2f}" y2="{canvas_h - margin}" stroke="#eeeeee" stroke-width="1"/>')
        out.append(f'<text x="{xx + 4:.2f}" y="{canvas_h - margin + 22}" font-family="Arial" font-size="11" fill="#999">{gx}</text>')
        gx += grid_step

    gy = int(y0 // grid_step) * grid_step
    while gy <= y1:
        yy = sy(gy)
        out.append(f'<line x1="{margin}" y1="{yy:.2f}" x2="{canvas_w - margin}" y2="{yy:.2f}" stroke="#eeeeee" stroke-width="1"/>')
        out.append(f'<text x="{margin - 60}" y="{yy + 4:.2f}" font-family="Arial" font-size="11" fill="#999">{gy}</text>')
        gy += grid_step

    for ent in all_ents:
        typ = entity_type(ent)
        lay = layer(ent)
        original_lay = lay.replace("PIANTA_", "").replace("_", " ")
        col = COLORS.get(lay, COLORS.get(original_lay, "#777777"))
        if lay == "RITAGLIO_PIANTA":
            col = "#ff0000"

        pts = points_from_entity(ent)

        sw = 1.8
        if lay == "RITAGLIO_PIANTA":
            sw = 3.0

        if typ == "LINE" and len(pts) >= 2:
            (x_a, y_a), (x_b, y_b) = pts[0], pts[1]
            out.append(
                f'<line x1="{sx(x_a):.2f}" y1="{sy(y_a):.2f}" x2="{sx(x_b):.2f}" y2="{sy(y_b):.2f}" '
                f'stroke="{col}" stroke-width="{sw}" fill="none" opacity="0.92"/>'
            )

        elif typ in {"LWPOLYLINE", "POLYLINE"} and len(pts) >= 2:
            poly_pts = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in pts)
            out.append(
                f'<polyline points="{poly_pts}" stroke="{col}" stroke-width="{sw}" fill="none" opacity="0.92"/>'
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
                    f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="{r * scale:.2f}" '
                    f'stroke="{col}" stroke-width="1.4" fill="none" opacity="0.85"/>'
                )

    out.append('<rect x="20" y="20" width="850" height="82" fill="white" stroke="#cccccc"/>')
    out.append('<text x="40" y="52" font-family="Arial" font-size="22" fill="#222">Pianta centrale isolata - sezioni capriate escluse</text>')
    out.append(
        f'<text x="40" y="82" font-family="Arial" font-size="14" fill="#555">Crop: X {X_MIN_PIANTA}..{X_MAX_PIANTA}, Y {Y_MIN_PIANTA}..{Y_MAX_PIANTA}</text>'
    )

    out.append("</svg>")
    OUT_SVG.write_text("\n".join(out), encoding="utf-8")


def main():
    all_ents = entities(read_groups(DXF))
    plan_ents = [ent for ent in all_ents if is_plan_entity(ent)]

    write_groups(OUT_DXF, make_dxf(plan_ents))
    write_svg(plan_ents)

    counts = Counter(layer(ent) for ent in plan_ents)
    types = Counter(entity_type(ent) for ent in plan_ents)
    box = bbox(plan_ents)

    report = []
    report.append("PIANTA CENTRALE ISOLATA")
    report.append("=" * 26)
    report.append(f"Input: {DXF.resolve()}")
    report.append(f"Output SVG: {OUT_SVG.resolve()}")
    report.append(f"Output DXF: {OUT_DXF.resolve()}")
    report.append("")
    report.append(f"Crop X: {X_MIN_PIANTA}..{X_MAX_PIANTA}")
    report.append(f"Crop Y: {Y_MIN_PIANTA}..{Y_MAX_PIANTA}")
    report.append(f"Entita pianta: {len(plan_ents)}")
    report.append(f"BBox pianta: {box}")
    report.append("")
    report.append("Layer:")
    for k, v in sorted(counts.items()):
        report.append(f"- {k}: {v}")
    report.append("")
    report.append("Tipi:")
    for k, v in sorted(types.items()):
        report.append(f"- {k}: {v}")

    OUT_TXT.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(OUT_SVG.resolve())
    print(OUT_DXF.resolve())
    print(OUT_TXT.resolve())


if __name__ == "__main__":
    main()