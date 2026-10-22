from __future__ import annotations

from pathlib import Path
from collections import Counter


DXF = Path("BERRA PLANIMETRIE PT_P1_COPERTURA_AGGIORNATA_220626.dxf")

OUT_LEFT_SVG = Path("berra_tavola_sinistra_base.svg")
OUT_RIGHT_SVG = Path("berra_tavola_destra_nuovo.svg")
OUT_TXT = Path("berra_tavole_separate_report.txt")

X_CODES = {"10", "11", "12", "13"}
Y_CODES = {"20", "21", "22", "23"}

LEFT_X_RANGE = (2500, 8500)
RIGHT_X_RANGE = (25000, 33000)

SKIP_TYPES = {
    "TEXT",
    "MTEXT",
    "DIMENSION",
    "MULTILEADER",
    "HATCH",
}

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

RIGHT_LAYERS = {
    "Nuovo_Strutturale - Portante",
    "Nuovo_BERRA_V06_VERDE_ARREDI",
    "Nuovo_Interni - Arredo",
    "Nuovo_Disegno 2D - Generale_Num_Penna__62",
    "BERRA_V12_FINITURE_APERTURE_ASSIALI",
    "Nuovo_BERRA_V12_FINITURE_APERTURE_ASSIALI",
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
    "Nuovo_Strutturale - Portante": "#d62728",
    "Nuovo_BERRA_V06_VERDE_ARREDI": "#228B3B",
    "Nuovo_Interni - Arredo": "#1f77b4",
    "Nuovo_Disegno 2D - Generale_Num_Penna__62": "#9467bd",
    "BERRA_V12_FINITURE_APERTURE_ASSIALI": "#ff7f0e",
    "Nuovo_BERRA_V12_FINITURE_APERTURE_ASSIALI": "#ff7f0e",
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


def is_left(ent: list[tuple[str, str]]) -> bool:
    if entity_type(ent) in SKIP_TYPES:
        return False

    if layer(ent) not in LEFT_LAYERS:
        return False

    cx = entity_center_x(ent)
    if cx is None:
        return False

    return LEFT_X_RANGE[0] <= cx <= LEFT_X_RANGE[1]


def is_right(ent: list[tuple[str, str]]) -> bool:
    if entity_type(ent) in SKIP_TYPES:
        return False

    if layer(ent) not in RIGHT_LAYERS:
        return False

    cx = entity_center_x(ent)
    if cx is None:
        return False

    return RIGHT_X_RANGE[0] <= cx <= RIGHT_X_RANGE[1]


def write_svg(ents: list[list[tuple[str, str]]], out_path: Path, title: str):
    box = bbox(ents)

    if box is None:
        out_path.write_text("<svg></svg>", encoding="utf-8")
        return

    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    pad = max(w, h) * 0.05

    view_x = x0 - pad
    view_y = -(y1 + pad)
    view_w = w + pad * 2
    view_h = h + pad * 2

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_x:.3f} {view_y:.3f} {view_w:.3f} {view_h:.3f}" width="1300" height="1000">'
    )
    out.append(
        f'<rect x="{view_x:.3f}" y="{view_y:.3f}" width="{view_w:.3f}" height="{view_h:.3f}" fill="#fafafa"/>'
    )

    # griglia
    grid_step = 1000
    gx = int((x0 - pad) // grid_step) * grid_step
    while gx <= x1 + pad:
        out.append(
            f'<line x1="{gx:.3f}" y1="{view_y:.3f}" x2="{gx:.3f}" y2="{view_y + view_h:.3f}" stroke="#eeeeee" stroke-width="8"/>'
        )
        gx += grid_step

    gy = int((y0 - pad) // grid_step) * grid_step
    while gy <= y1 + pad:
        out.append(
            f'<line x1="{view_x:.3f}" y1="{-gy:.3f}" x2="{view_x + view_w:.3f}" y2="{-gy:.3f}" stroke="#eeeeee" stroke-width="8"/>'
        )
        gy += grid_step

    for ent in ents:
        typ = entity_type(ent)
        lay = layer(ent)
        col = COLORS.get(lay, "#777777")
        pts = points_from_entity(ent)

        if typ == "LINE" and len(pts) >= 2:
            (x_a, y_a), (x_b, y_b) = pts[0], pts[1]
            out.append(
                f'<line x1="{x_a:.3f}" y1="{-y_a:.3f}" x2="{x_b:.3f}" y2="{-y_b:.3f}" '
                f'stroke="{col}" stroke-width="14" fill="none" opacity="0.92"/>'
            )

        elif typ in {"LWPOLYLINE", "POLYLINE"} and len(pts) >= 2:
            poly_pts = " ".join(f"{x:.3f},{-y:.3f}" for x, y in pts)
            out.append(
                f'<polyline points="{poly_pts}" stroke="{col}" stroke-width="14" fill="none" opacity="0.92"/>'
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
                    f'stroke="{col}" stroke-width="14" fill="none" opacity="0.85"/>'
                )

    # titolo
    tx = view_x + pad * 0.6
    ty = view_y + pad * 0.8
    out.append(
        f'<rect x="{tx:.3f}" y="{ty:.3f}" width="{view_w * 0.55:.3f}" height="{pad * 0.9:.3f}" fill="white" stroke="#cccccc" stroke-width="8" opacity="0.92"/>'
    )
    out.append(
        f'<text x="{tx + pad * 0.2:.3f}" y="{ty + pad * 0.55:.3f}" font-size="{pad * 0.22:.3f}" font-family="Arial" fill="#222222">{title}</text>'
    )

    out.append("</svg>")
    out_path.write_text("\n".join(out), encoding="utf-8")


def summarize(name: str, ents: list[list[tuple[str, str]]]) -> list[str]:
    lines = []
    box = bbox(ents)
    counts = Counter(layer(ent) for ent in ents)
    types = Counter(entity_type(ent) for ent in ents)

    lines.append(name)
    lines.append("-" * len(name))
    lines.append(f"Entita: {len(ents)}")
    lines.append(f"BBox: {box}")

    if box:
        x0, y0, x1, y1 = box
        lines.append(f"Dimensioni: {x1 - x0:.3f} x {y1 - y0:.3f}")

    lines.append("Layer:")
    for k, v in sorted(counts.items()):
        lines.append(f"- {k}: {v}")

    lines.append("Tipi:")
    for k, v in sorted(types.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    return lines


def main():
    all_ents = entities(read_groups(DXF))

    left = [ent for ent in all_ents if is_left(ent)]
    right = [ent for ent in all_ents if is_right(ent)]

    write_svg(left, OUT_LEFT_SVG, "Tavola sinistra / base coperture-struttura")
    write_svg(right, OUT_RIGHT_SVG, "Tavola destra / nuovo rilievo")

    report = []
    report.append("DXF BERRA - TAVOLE SEPARATE")
    report.append("=" * 34)
    report.append(f"File: {DXF.resolve()}")
    report.append("")
    report += summarize("TAVOLA SINISTRA / BASE", left)
    report += summarize("TAVOLA DESTRA / NUOVO", right)

    OUT_TXT.write_text("\n".join(report), encoding="utf-8")

    print("Generate preview tavole separate:")
    print(OUT_LEFT_SVG.resolve())
    print(OUT_RIGHT_SVG.resolve())
    print(OUT_TXT.resolve())


if __name__ == "__main__":
    main()