from __future__ import annotations

from pathlib import Path
from collections import Counter


DXF = Path("BERRA PLANIMETRIE PT_P1_COPERTURA_AGGIORNATA_220626.dxf")

OUT_DXF = Path("berra_tavola_sinistra_calibrata_archicad.dxf")
OUT_SVG = Path("berra_tavola_sinistra_calibrata_archicad.svg")
OUT_TXT = Path("berra_tavola_sinistra_calibrata_archicad_report.txt")

# BBox tavola sinistra/base da report
DXF_X_MIN = 3077.550253634036
DXF_Y_MIN = 1086.045186813598
DXF_X_MAX = 7572.913700231609
DXF_Y_MAX = 15859.86690767404

# Rettangolo reale planimetria in coordinate Archicad/metri
# basso sinistro = -69.91, -74.95
# basso destro   = -5.05,  -74.95
# alto destro    = -5.05,   35.37
# alto sinistro  = -70.07,  35.37
AC_X_MIN = -69.91
AC_Y_MIN = -74.95
AC_X_MAX = -5.05
AC_Y_MAX = 35.37

LEFT_X_RANGE = (2500, 8500)

X_CODES = {"10", "11", "12", "13"}
Y_CODES = {"20", "21", "22", "23"}

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

LAYER_COLORS = {
    "CAL_00_STRUTTURE_MURI": 7,
    "CAL_MURATURE": 8,
    "CAL_B_COPERTURA": 6,
    "CAL_B_TRAVI": 30,
    "CAL_CAPRIATE_LEGNO": 30,
    "CAL_METALLI": 5,
    "CAL_B_ASSITI": 34,
    "CAL_C_MENSOLE": 32,
    "CAL_B_VISTE": 9,
    "ARCHICAD_BBOX_RIF": 1,
}

SVG_COLORS = {
    "CAL_00_STRUTTURE_MURI": "#111111",
    "CAL_MURATURE": "#444444",
    "CAL_B_COPERTURA": "#7B3FB2",
    "CAL_B_TRAVI": "#9a6a2f",
    "CAL_CAPRIATE_LEGNO": "#b56a2f",
    "CAL_METALLI": "#517a9b",
    "CAL_B_ASSITI": "#6f4e37",
    "CAL_C_MENSOLE": "#aa6f39",
    "CAL_B_VISTE": "#999999",
    "ARCHICAD_BBOX_RIF": "#d62728",
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

    cx = entity_center_x(ent)
    if cx is None:
        return False

    return LEFT_X_RANGE[0] <= cx <= LEFT_X_RANGE[1]


def transform_xy(x: float, y: float) -> tuple[float, float]:
    sx = (AC_X_MAX - AC_X_MIN) / (DXF_X_MAX - DXF_X_MIN)
    sy = (AC_Y_MAX - AC_Y_MIN) / (DXF_Y_MAX - DXF_Y_MIN)

    x2 = AC_X_MIN + (x - DXF_X_MIN) * sx
    y2 = AC_Y_MIN + (y - DXF_Y_MIN) * sy

    return x2, y2


def transform_radius(r: float) -> float:
    sx = abs((AC_X_MAX - AC_X_MIN) / (DXF_X_MAX - DXF_X_MIN))
    sy = abs((AC_Y_MAX - AC_Y_MIN) / (DXF_Y_MAX - DXF_Y_MIN))
    return r * (sx + sy) / 2


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


def transform_entity(ent: list[tuple[str, str]]) -> list[tuple[str, str]]:
    out = []
    pending_x_index = None

    for code, value in ent:
        n = numeric(value)

        if n is not None and code in X_CODES:
            # trasformo la X solo quando trovo la Y corrispondente
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

    return set_layer(out, f"CAL_{layer(ent).replace(' ', '_').replace('-', '_')}")


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


def layer_table() -> list[tuple[str, str]]:
    out = [("0", "TABLE"), ("2", "LAYER"), ("70", str(len(LAYER_COLORS)))]

    for name, color in LAYER_COLORS.items():
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
        ("10", f"{x1:.6f}"),
        ("20", f"{y1:.6f}"),
        ("30", "0"),
        ("11", f"{x2:.6f}"),
        ("21", f"{y2:.6f}"),
        ("31", "0"),
    ]


def archicad_bbox_entities() -> list[list[tuple[str, str]]]:
    pts = [
        (AC_X_MIN, AC_Y_MIN),
        (AC_X_MAX, AC_Y_MIN),
        (AC_X_MAX, AC_Y_MAX),
        (AC_X_MIN, AC_Y_MAX),
    ]

    ents = []

    for a, b in zip(pts, pts[1:] + pts[:1]):
        ents.append(dxf_line("ARCHICAD_BBOX_RIF", a[0], a[1], b[0], b[1]))

    return ents


def make_dxf(calibrated: list[list[tuple[str, str]]]) -> list[tuple[str, str]]:
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

    for ent in calibrated:
        out += ent

    for ent in archicad_bbox_entities():
        out += ent

    out += [
        ("0", "ENDSEC"),
        ("0", "EOF"),
    ]
    return out


def write_svg(calibrated: list[list[tuple[str, str]]]) -> None:
    all_ents = calibrated + archicad_bbox_entities()
    box = bbox(all_ents)

    if box is None:
        OUT_SVG.write_text("<svg></svg>", encoding="utf-8")
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
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_x:.3f} {view_y:.3f} {view_w:.3f} {view_h:.3f}" width="1200" height="1600">'
    )
    out.append(
        f'<rect x="{view_x:.3f}" y="{view_y:.3f}" width="{view_w:.3f}" height="{view_h:.3f}" fill="#fafafa"/>'
    )

    for ent in all_ents:
        typ = entity_type(ent)
        lay = layer(ent)
        col = SVG_COLORS.get(lay, "#777777")
        pts = points_from_entity(ent)

        sw = 0.12
        if lay == "ARCHICAD_BBOX_RIF":
            sw = 0.35

        if typ == "LINE" and len(pts) >= 2:
            (x_a, y_a), (x_b, y_b) = pts[0], pts[1]
            out.append(
                f'<line x1="{x_a:.6f}" y1="{-y_a:.6f}" x2="{x_b:.6f}" y2="{-y_b:.6f}" '
                f'stroke="{col}" stroke-width="{sw}" fill="none" opacity="0.92"/>'
            )

        elif typ in {"LWPOLYLINE", "POLYLINE"} and len(pts) >= 2:
            poly_pts = " ".join(f"{x:.6f},{-y:.6f}" for x, y in pts)
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
                    f'<circle cx="{x:.6f}" cy="{-y:.6f}" r="{r:.6f}" '
                    f'stroke="{col}" stroke-width="{sw}" fill="none" opacity="0.85"/>'
                )

    out.append("</svg>")
    OUT_SVG.write_text("\n".join(out), encoding="utf-8")


def main():
    all_ents = entities(read_groups(DXF))
    left = [ent for ent in all_ents if is_left_entity(ent)]
    calibrated = [transform_entity(ent) for ent in left]

    write_groups(OUT_DXF, make_dxf(calibrated))
    write_svg(calibrated)

    sx = (AC_X_MAX - AC_X_MIN) / (DXF_X_MAX - DXF_X_MIN)
    sy = (AC_Y_MAX - AC_Y_MIN) / (DXF_Y_MAX - DXF_Y_MIN)

    counts = Counter(layer(ent) for ent in calibrated)

    report = []
    report.append("CALIBRAZIONE TAVOLA SINISTRA DXF -> ARCHICAD")
    report.append("=" * 52)
    report.append(f"Input DXF: {DXF.resolve()}")
    report.append(f"Output DXF: {OUT_DXF.resolve()}")
    report.append(f"Output SVG: {OUT_SVG.resolve()}")
    report.append("")
    report.append(f"BBox DXF sinistra: {(DXF_X_MIN, DXF_Y_MIN, DXF_X_MAX, DXF_Y_MAX)}")
    report.append(f"BBox Archicad rif: {(AC_X_MIN, AC_Y_MIN, AC_X_MAX, AC_Y_MAX)}")
    report.append(f"Scala X: {sx:.9f}")
    report.append(f"Scala Y: {sy:.9f}")
    report.append("")
    report.append("ATTENZIONE:")
    report.append("- Questa calibrazione usa solo il bounding box, quindi puo deformare se la tavola DXF non corrisponde perfettamente all'ingombro Archicad.")
    report.append("- Serve come prima verifica visiva. La calibrazione finale andra fatta con punti omologhi.")
    report.append("")
    report.append("Entita calibrate per layer:")
    for k, v in sorted(counts.items()):
        report.append(f"- {k}: {v}")

    OUT_TXT.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(OUT_DXF.resolve())
    print(OUT_SVG.resolve())
    print(OUT_TXT.resolve())


if __name__ == "__main__":
    main()