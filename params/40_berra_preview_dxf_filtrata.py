from __future__ import annotations

from pathlib import Path
from collections import Counter


DXF = Path("BERRA PLANIMETRIE PT_P1_COPERTURA_AGGIORNATA_220626.dxf")
OUT_SVG = Path("berra_preview_dxf_filtrata_corpo_principale.svg")
OUT_TXT = Path("berra_preview_dxf_filtrata_corpo_principale.txt")

KEEP_LAYERS = {
    "00_STRUTTURE MURI",
    "MURATURE",
    "B_COPERTURA",
    "B_TRAVI",
    "CAPRIATE_LEGNO",
    "METALLI",
    "Nuovo_Strutturale - Portante",
    "Nuovo_BERRA_V06_VERDE_ARREDI",
}

SKIP_TYPES = {
    "TEXT",
    "MTEXT",
    "DIMENSION",
    "MULTILEADER",
    "HATCH",
}

X_CODES = {"10", "11", "12", "13"}
Y_CODES = {"20", "21", "22", "23"}

COLORS = {
    "00_STRUTTURE MURI": "#111111",
    "MURATURE": "#444444",
    "B_COPERTURA": "#7B3FB2",
    "B_TRAVI": "#9a6a2f",
    "CAPRIATE_LEGNO": "#b56a2f",
    "METALLI": "#517a9b",
    "Nuovo_Strutturale - Portante": "#d62728",
    "Nuovo_BERRA_V06_VERDE_ARREDI": "#228B3B",
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


def is_useful(ent: list[tuple[str, str]]) -> bool:
    lay = layer(ent)
    typ = entity_type(ent)

    if lay not in KEEP_LAYERS:
        return False

    if typ in SKIP_TYPES:
        return False

    pts = points_from_entity(ent)
    if len(pts) < 1:
        return False

    return True


def write_svg(ents: list[list[tuple[str, str]]]):
    box = bbox(ents)
    if box is None:
        OUT_SVG.write_text("<svg></svg>", encoding="utf-8")
        return

    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0

    pad = max(w, h) * 0.04

    view_x = x0 - pad
    view_y = -(y1 + pad)
    view_w = w + pad * 2
    view_h = h + pad * 2

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_x:.3f} {view_y:.3f} {view_w:.3f} {view_h:.3f}" width="1400" height="1000">'
    )
    out.append(
        f'<rect x="{view_x:.3f}" y="{view_y:.3f}" width="{view_w:.3f}" height="{view_h:.3f}" fill="#fafafa"/>'
    )

    # griglia leggera
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
                f'stroke="{col}" stroke-width="18" fill="none" opacity="0.90"/>'
            )

        elif typ in {"LWPOLYLINE", "POLYLINE"} and len(pts) >= 2:
            poly_pts = " ".join(f"{x:.3f},{-y:.3f}" for x, y in pts)
            out.append(
                f'<polyline points="{poly_pts}" stroke="{col}" stroke-width="18" fill="none" opacity="0.90"/>'
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
                    f'stroke="{col}" stroke-width="18" fill="none" opacity="0.80"/>'
                )

    # legenda
    lx = view_x + pad
    ly = view_y + pad

    out.append(
        f'<rect x="{lx:.3f}" y="{ly:.3f}" width="{view_w * 0.38:.3f}" height="{len(KEEP_LAYERS) * 190 + 220:.3f}" '
        f'fill="white" stroke="#cccccc" stroke-width="10" opacity="0.92"/>'
    )
    out.append(
        f'<text x="{lx + 120:.3f}" y="{ly + 140:.3f}" font-size="150" font-family="Arial" fill="#222222">DXF Berra - Preview filtrata</text>'
    )

    for i, layer_name in enumerate(sorted(KEEP_LAYERS)):
        yy = ly + 310 + i * 180
        col = COLORS.get(layer_name, "#777777")
        out.append(
            f'<line x1="{lx + 120:.3f}" y1="{yy:.3f}" x2="{lx + 420:.3f}" y2="{yy:.3f}" stroke="{col}" stroke-width="35"/>'
        )
        out.append(
            f'<text x="{lx + 480:.3f}" y="{yy + 45:.3f}" font-size="120" font-family="Arial" fill="#222222">{layer_name}</text>'
        )

    out.append("</svg>")
    OUT_SVG.write_text("\n".join(out), encoding="utf-8")


def main():
    all_ents = entities(read_groups(DXF))
    filtered = [ent for ent in all_ents if is_useful(ent)]

    counts = Counter(layer(ent) for ent in filtered)
    type_counts = Counter(entity_type(ent) for ent in filtered)
    box = bbox(filtered)

    report = []
    report.append("PREVIEW FILTRATA DXF BERRA")
    report.append("=" * 32)
    report.append(f"File: {DXF.resolve()}")
    report.append(f"Entita totali DXF: {len(all_ents)}")
    report.append(f"Entita filtrate: {len(filtered)}")
    report.append(f"BBox filtrato: {box}")

    if box:
        x0, y0, x1, y1 = box
        report.append(f"Dimensione filtrata: {x1 - x0:.3f} x {y1 - y0:.3f}")

    report.append("")
    report.append("Entita per layer:")
    for k, v in sorted(counts.items()):
        report.append(f"- {k}: {v}")

    report.append("")
    report.append("Entita per tipo:")
    for k, v in sorted(type_counts.items()):
        report.append(f"- {k}: {v}")

    OUT_TXT.write_text("\n".join(report) + "\n", encoding="utf-8")
    write_svg(filtered)

    print("Preview filtrata generata:")
    print(OUT_SVG.resolve())
    print(OUT_TXT.resolve())


if __name__ == "__main__":
    main()