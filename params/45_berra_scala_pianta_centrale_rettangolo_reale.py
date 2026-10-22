from __future__ import annotations

from pathlib import Path
from collections import Counter


IN_DXF = Path("berra_pianta_centrale_isolata.dxf")

OUT_DXF = Path("berra_pianta_centrale_rettangolo_reale.dxf")
OUT_SVG = Path("berra_pianta_centrale_rettangolo_reale.svg")
OUT_TXT = Path("berra_pianta_centrale_rettangolo_reale_report.txt")

X_CODES = {"10", "11", "12", "13"}
Y_CODES = {"20", "21", "22", "23"}

# Rettangolo reale fornito dall'utente, in metri / coordinate Archicad.
REAL_X_MIN = -69.91
REAL_Y_MIN = -74.95
REAL_X_MAX = -5.05
REAL_Y_MAX = 35.37

# Nota: alto sinistro reale = -70.07, 35.37.
# Per ora usiamo rettangolo ortogonale medio; la piccola differenza di 0.16 m
# verrà gestita dopo con punti omologhi se necessario.

SKIP_TYPES = {
    "TEXT",
    "MTEXT",
    "DIMENSION",
    "MULTILEADER",
    "HATCH",
}

SVG_COLORS = {
    "PIANTA_00_STRUTTURE_MURI": "#111111",
    "PIANTA_MURATURE": "#444444",
    "PIANTA_B_COPERTURA": "#7B3FB2",
    "PIANTA_B_TRAVI": "#9a6a2f",
    "PIANTA_METALLI": "#517a9b",
    "PIANTA_B_ASSITI": "#6f4e37",
    "PIANTA_B_VISTE": "#999999",
    "RITAGLIO_PIANTA": "#ff0000",
    "RETANGOLO_REALE": "#d62728",
}

DXF_LAYER_COLORS = {
    "REAL_PIANTA_00_STRUTTURE_MURI": 7,
    "REAL_PIANTA_MURATURE": 8,
    "REAL_PIANTA_B_COPERTURA": 6,
    "REAL_PIANTA_B_TRAVI": 30,
    "REAL_PIANTA_METALLI": 5,
    "REAL_PIANTA_B_ASSITI": 34,
    "REAL_PIANTA_B_VISTE": 9,
    "REAL_RITAGLIO_PIANTA": 1,
    "RETANGOLO_REALE": 1,
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


def clean_entities(ents: list[list[tuple[str, str]]]) -> list[list[tuple[str, str]]]:
    out = []

    for ent in ents:
        typ = entity_type(ent)
        lay = layer(ent)

        if typ in SKIP_TYPES:
            continue

        # Esclude il vecchio rettangolo di ritaglio generato dallo script 44.
        if lay == "RITAGLIO_PIANTA":
            continue

        if not points_from_entity(ent):
            continue

        out.append(ent)

    return out


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


def make_transform(source_box: tuple[float, float, float, float]):
    sx0, sy0, sx1, sy1 = source_box

    scale_x = (REAL_X_MAX - REAL_X_MIN) / (sx1 - sx0)
    scale_y = (REAL_Y_MAX - REAL_Y_MIN) / (sy1 - sy0)

    def transform_xy(x: float, y: float) -> tuple[float, float]:
        x2 = REAL_X_MIN + (x - sx0) * scale_x
        y2 = REAL_Y_MIN + (y - sy0) * scale_y
        return x2, y2

    def transform_radius(r: float) -> float:
        return r * (abs(scale_x) + abs(scale_y)) / 2.0

    return transform_xy, transform_radius, scale_x, scale_y


def transform_entity(ent: list[tuple[str, str]], transform_xy, transform_radius) -> list[tuple[str, str]]:
    out = []
    pending_x_index = None

    for code, value in ent:
        n = numeric(value)

        if n is not None and code in X_CODES:
            out.append((code, value))
            pending_x_index = len(out) - 1

        elif n is not None and code in Y_CODES and pending_x_index is not None:
            old_x = numeric(out[pending_x_index][1])
            old_y = n

            if old_x is not None:
                new_x, new_y = transform_xy(old_x, old_y)
                old_x_code = out[pending_x_index][0]
                out[pending_x_index] = (old_x_code, f"{new_x:.6f}")
                out.append((code, f"{new_y:.6f}"))
            else:
                out.append((code, value))

            pending_x_index = None

        elif n is not None and code == "40":
            out.append((code, f"{transform_radius(n):.6f}"))

        else:
            out.append((code, value))

    old_layer = layer(ent)
    new_layer = "REAL_" + old_layer.replace(" ", "_").replace("-", "_")
    return set_layer(out, new_layer)


def dxf_line(layer_name: str, x1: float, y1: float, x2: float, y2: float) -> list[tuple[str, str]]:
    return [
        ("0", "LINE"),
        ("8", layer_name),
        ("10", f"{x1:.6f}"),
        ("20", f"{y1:.6f}"),
        ("30", "0"),
        ("11", f"{x2:.6f}"),
        ("21", f"{y2:.6f}"),
        ("31", "0"),
    ]


def real_rectangle_entities() -> list[list[tuple[str, str]]]:
    pts = [
        (REAL_X_MIN, REAL_Y_MIN),
        (REAL_X_MAX, REAL_Y_MIN),
        (REAL_X_MAX, REAL_Y_MAX),
        (REAL_X_MIN, REAL_Y_MAX),
    ]

    return [
        dxf_line("RETANGOLO_REALE", a[0], a[1], b[0], b[1])
        for a, b in zip(pts, pts[1:] + pts[:1])
    ]


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


def make_dxf(real_ents: list[list[tuple[str, str]]]) -> list[tuple[str, str]]:
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

    for ent in real_ents:
        out += ent

    for ent in real_rectangle_entities():
        out += ent

    out += [
        ("0", "ENDSEC"),
        ("0", "EOF"),
    ]

    return out


def write_svg(real_ents: list[list[tuple[str, str]]]) -> None:
    all_ents = real_ents + real_rectangle_entities()
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

    # Griglia metrica ogni 10 m
    grid_step = 10.0
    gx = int(x0 // grid_step) * grid_step
    while gx <= x1:
        xx = sx(gx)
        out.append(f'<line x1="{xx:.2f}" y1="{margin}" x2="{xx:.2f}" y2="{canvas_h - margin}" stroke="#eeeeee" stroke-width="1"/>')
        out.append(f'<text x="{xx + 4:.2f}" y="{canvas_h - margin + 22}" font-family="Arial" font-size="11" fill="#999">{gx:.0f}</text>')
        gx += grid_step

    gy = int(y0 // grid_step) * grid_step
    while gy <= y1:
        yy = sy(gy)
        out.append(f'<line x1="{margin}" y1="{yy:.2f}" x2="{canvas_w - margin}" y2="{yy:.2f}" stroke="#eeeeee" stroke-width="1"/>')
        out.append(f'<text x="{margin - 55}" y="{yy + 4:.2f}" font-family="Arial" font-size="11" fill="#999">{gy:.0f}</text>')
        gy += grid_step

    for ent in all_ents:
        typ = entity_type(ent)
        lay = layer(ent)
        base_lay = lay.replace("REAL_", "")
        col = SVG_COLORS.get(base_lay, SVG_COLORS.get(lay, "#777777"))
        pts = points_from_entity(ent)

        sw = 1.5
        if lay == "RETANGOLO_REALE":
            sw = 3.0
            col = "#d62728"

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
                    f'stroke="{col}" stroke-width="1.2" fill="none" opacity="0.85"/>'
                )

    out.append('<rect x="20" y="20" width="850" height="90" fill="white" stroke="#cccccc"/>')
    out.append('<text x="40" y="55" font-family="Arial" font-size="22" fill="#222">Pianta centrale scalata nel rettangolo reale</text>')
    out.append(
        f'<text x="40" y="85" font-family="Arial" font-size="14" fill="#555">Rettangolo reale: X {REAL_X_MIN}..{REAL_X_MAX}, Y {REAL_Y_MIN}..{REAL_Y_MAX}</text>'
    )

    out.append("</svg>")
    OUT_SVG.write_text("\n".join(out), encoding="utf-8")


def main():
    raw_ents = entities(read_groups(IN_DXF))
    clean = clean_entities(raw_ents)
    source_box = bbox(clean)

    if source_box is None:
        raise RuntimeError("Nessuna entità utile trovata nel DXF isolato.")

    transform_xy, transform_radius, scale_x, scale_y = make_transform(source_box)

    real_ents = [
        transform_entity(ent, transform_xy, transform_radius)
        for ent in clean
    ]

    write_groups(OUT_DXF, make_dxf(real_ents))
    write_svg(real_ents)

    counts = Counter(layer(ent) for ent in real_ents)
    types = Counter(entity_type(ent) for ent in real_ents)
    out_box = bbox(real_ents)

    report = []
    report.append("SCALA PIANTA CENTRALE SU RETTANGOLO REALE")
    report.append("=" * 48)
    report.append(f"Input: {IN_DXF.resolve()}")
    report.append(f"Output DXF: {OUT_DXF.resolve()}")
    report.append(f"Output SVG: {OUT_SVG.resolve()}")
    report.append("")
    report.append(f"BBox sorgente isolata: {source_box}")
    report.append(f"Rettangolo reale usato: {(REAL_X_MIN, REAL_Y_MIN, REAL_X_MAX, REAL_Y_MAX)}")
    report.append(f"Output bbox: {out_box}")
    report.append("")
    report.append(f"Scala X: {scale_x:.9f}")
    report.append(f"Scala Y: {scale_y:.9f}")
    report.append("")
    report.append("Nota:")
    report.append("- Questo file usa solo la pianta centrale isolata.")
    report.append("- Il lato sinistro reale ha una piccola differenza tra basso e alto (-69.91 / -70.07), non applicata in questa prima versione.")
    report.append("- Se necessario, la correggiamo con punti omologhi.")
    report.append("")
    report.append("Entità per layer:")
    for k, v in sorted(counts.items()):
        report.append(f"- {k}: {v}")
    report.append("")
    report.append("Entità per tipo:")
    for k, v in sorted(types.items()):
        report.append(f"- {k}: {v}")

    OUT_TXT.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(OUT_DXF.resolve())
    print(OUT_SVG.resolve())
    print(OUT_TXT.resolve())


if __name__ == "__main__":
    main()