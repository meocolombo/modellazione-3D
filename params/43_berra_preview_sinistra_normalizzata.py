from __future__ import annotations

from pathlib import Path
from collections import Counter


DXF = Path("BERRA PLANIMETRIE PT_P1_COPERTURA_AGGIORNATA_220626.dxf")

OUT_SVG = Path("berra_tavola_sinistra_normalizzata_punti.svg")
OUT_TXT = Path("berra_tavola_sinistra_normalizzata_punti_report.txt")

X_CODES = {"10", "11", "12", "13"}
Y_CODES = {"20", "21", "22", "23"}

LEFT_X_RANGE = (2500, 8500)

LEFT_LAYERS = {
    "00_STRUTTURE MURI",
    "MURATURE",
    "B_COPERTURA",
    "B_TRAVI",
    "CAPRIATE_LEGNO",
    "METALLI",
    "B_ASSITI",
    "C_MENSOLE",
    "B_VISTE",
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
    "CAPRIATE_LEGNO": "#b56a2f",
    "METALLI": "#517a9b",
    "B_ASSITI": "#6f4e37",
    "C_MENSOLE": "#aa6f39",
    "B_VISTE": "#999999",
}


def read_groups(path: Path) -> list[tuple[str, str]]:
    raw = path.read_text(encoding="ascii", errors="ignore").splitlines()
    return [(raw[i].strip(), raw[i + 1].strip()) for i in range(0, len(raw) - 1, 2)]


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


def entity_center_x(ent: list[tuple[str, str]]) -> float | None:
    pts = points_from_entity(ent)
    if not pts:
        return None
    return sum(x for x, _ in pts) / len(pts)


def is_left_entity(ent: list[tuple[str, str]]) -> bool:
    typ = entity_type(ent)
    lay = layer(ent)

    if typ in SKIP_TYPES:
        return False

    if lay not in LEFT_LAYERS:
        return False

    pts = points_from_entity(ent)
    if not pts:
        return False

    cx = entity_center_x(ent)
    if cx is None:
        return False

    return LEFT_X_RANGE[0] <= cx <= LEFT_X_RANGE[1]


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


def candidate_points(box: tuple[float, float, float, float]) -> list[tuple[str, float, float]]:
    x0, y0, x1, y1 = box

    # Punti guida iniziali su bbox + centro. Servono solo per orientarsi visivamente.
    return [
        ("P1_SW_bbox", x0, y0),
        ("P2_SE_bbox", x1, y0),
        ("P3_NE_bbox", x1, y1),
        ("P4_NW_bbox", x0, y1),
        ("P5_CENTRO_bbox", (x0 + x1) / 2, (y0 + y1) / 2),
        ("P6_MID_SUD", (x0 + x1) / 2, y0),
        ("P7_MID_NORD", (x0 + x1) / 2, y1),
    ]


def main():
    all_ents = entities(read_groups(DXF))
    left = [ent for ent in all_ents if is_left_entity(ent)]
    box = bbox(left)

    if box is None:
        raise RuntimeError("Nessuna entita utile trovata.")

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

    # Griglia normalizzata ogni 1000 unita DXF
    grid_step = 1000
    gx = int(x0 // grid_step) * grid_step
    while gx <= x1:
        xx = sx(gx)
        out.append(f'<line x1="{xx:.2f}" y1="{margin}" x2="{xx:.2f}" y2="{canvas_h - margin}" stroke="#eeeeee" stroke-width="1"/>')
        out.append(f'<text x="{xx + 4:.2f}" y="{canvas_h - margin + 22}" font-family="Arial" font-size="12" fill="#999">{gx}</text>')
        gx += grid_step

    gy = int(y0 // grid_step) * grid_step
    while gy <= y1:
        yy = sy(gy)
        out.append(f'<line x1="{margin}" y1="{yy:.2f}" x2="{canvas_w - margin}" y2="{yy:.2f}" stroke="#eeeeee" stroke-width="1"/>')
        out.append(f'<text x="{margin - 72}" y="{yy + 4:.2f}" font-family="Arial" font-size="12" fill="#999">{gy}</text>')
        gy += grid_step

    # Disegno entità
    for ent in left:
        typ = entity_type(ent)
        lay = layer(ent)
        col = COLORS.get(lay, "#777777")
        pts = points_from_entity(ent)

        if typ == "LINE" and len(pts) >= 2:
            (x_a, y_a), (x_b, y_b) = pts[0], pts[1]
            out.append(
                f'<line x1="{sx(x_a):.2f}" y1="{sy(y_a):.2f}" x2="{sx(x_b):.2f}" y2="{sy(y_b):.2f}" '
                f'stroke="{col}" stroke-width="1.6" fill="none" opacity="0.92"/>'
            )

        elif typ in {"LWPOLYLINE", "POLYLINE"} and len(pts) >= 2:
            poly_pts = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in pts)
            out.append(
                f'<polyline points="{poly_pts}" stroke="{col}" stroke-width="1.6" fill="none" opacity="0.92"/>'
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

    # Punti candidati bbox
    for name, x, y in candidate_points(box):
        xx = sx(x)
        yy = sy(y)
        out.append(f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="6" fill="#ff0000" stroke="white" stroke-width="2"/>')
        out.append(f'<text x="{xx + 10:.2f}" y="{yy - 10:.2f}" font-family="Arial" font-size="16" fill="#cc0000">{name}</text>')

    # Titolo
    out.append(f'<rect x="20" y="20" width="780" height="70" fill="white" stroke="#cccccc"/>')
    out.append(f'<text x="40" y="50" font-family="Arial" font-size="20" fill="#222">Tavola sinistra normalizzata - scegli punti omologhi</text>')
    out.append(f'<text x="40" y="76" font-family="Arial" font-size="14" fill="#555">BBox DXF: {box}</text>')

    out.append("</svg>")
    OUT_SVG.write_text("\n".join(out), encoding="utf-8")

    counts = Counter(layer(ent) for ent in left)

    report = []
    report.append("TAVOLA SINISTRA NORMALIZZATA")
    report.append("=" * 34)
    report.append(f"Input: {DXF.resolve()}")
    report.append(f"Output SVG: {OUT_SVG.resolve()}")
    report.append(f"Entita: {len(left)}")
    report.append(f"BBox: {box}")
    report.append(f"Scala preview px/unit: {scale:.8f}")
    report.append("")
    report.append("Layer:")
    for k, v in sorted(counts.items()):
        report.append(f"- {k}: {v}")
    report.append("")
    report.append("Punti candidati automatici:")
    for name, x, y in candidate_points(box):
        report.append(f"- {name}: dxf_x={x:.3f}, dxf_y={y:.3f}")

    OUT_TXT.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(OUT_SVG.resolve())
    print(OUT_TXT.resolve())


if __name__ == "__main__":
    main()