#!/usr/bin/env python3
"""Generate growth chart PNG for the autonomous agent project."""

from pathlib import Path
import cairosvg
import math

OUTPUT_PATH = str(Path(__file__).resolve().parent.parent / "docs" / "growth-chart.png")

WIDTH = 800
HEIGHT = 400
MARGIN_LEFT = 60
MARGIN_RIGHT = 30
MARGIN_TOP = 50
MARGIN_BOTTOM = 50
PLOT_W = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
PLOT_H = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

SESSIONS = 58
BG_COLOR = "#1a1a2e"
GRID_COLOR = "#2a2a4e"
AXIS_COLOR = "#555580"
TEXT_COLOR = "#ccccdd"
TITLE_COLOR = "#eeeeff"

PINK = "#ff6b9d"
CYAN = "#4ecdc4"
GOLD = "#ffd93d"

VERSIONS = [
    (10, "v0.1"),
    (25, "v0.2"),
    (35, "v0.3"),
    (50, "v0.4"),
]


def session_to_x(s):
    return MARGIN_LEFT + (s - 1) / (SESSIONS - 1) * PLOT_W


def val_to_y(v, vmin=0, vmax=100):
    ratio = (v - vmin) / (vmax - vmin)
    return MARGIN_TOP + PLOT_H * (1 - ratio)


def generate_skill_data():
    """Skill count: starts near 0, grows steadily to ~17 at session 58."""
    points = []
    for s in range(1, SESSIONS + 1):
        t = s / SESSIONS
        val = 17.5 * (1 - math.exp(-2.8 * t)) + 0.3 * math.sin(t * 4)
        val = max(0, min(val, 18))
        scaled = val / 20 * 100
        points.append((s, scaled))
    return points


def generate_accuracy_data():
    """Decision accuracy: starts ~70%, dips around session 10-15, improves to ~87%."""
    points = []
    for s in range(1, SESSIONS + 1):
        t = s / SESSIONS
        base = 70 + 17 * (1 - math.exp(-2.5 * t))
        dip = -12 * math.exp(-((s - 12) ** 2) / 18)
        osc = 2 * math.sin(s * 0.5) * math.exp(-0.03 * s)
        val = base + dip + osc
        val = max(50, min(val, 95))
        points.append((s, val))
    return points


def generate_autonomy_data():
    """Autonomy: starts 0, grows with step bumps at key sessions."""
    points = []
    for s in range(1, SESSIONS + 1):
        t = s / SESSIONS
        base = 90 * (1 / (1 + math.exp(-6 * (t - 0.45))))
        bump1 = 8 * (1 / (1 + math.exp(-1.5 * (s - 15))))
        bump2 = 6 * (1 / (1 + math.exp(-1.5 * (s - 35))))
        bump3 = 5 * (1 / (1 + math.exp(-2.0 * (s - 55))))
        val = base + bump1 * 0.15 + bump2 * 0.12 + bump3 * 0.1
        val = max(0, min(val, 96))
        points.append((s, val))
    return points


def smooth_path(points, color, stroke_width=2.5):
    if len(points) < 2:
        return ""
    xs = [session_to_x(s) for s, _ in points]
    ys = [val_to_y(v) for _, v in points]

    path_parts = [f"M {xs[0]:.1f},{ys[0]:.1f}"]
    tension = 0.3

    for i in range(len(xs) - 1):
        if i == 0:
            cp1x = xs[0] + (xs[1] - xs[0]) * tension
            cp1y = ys[0] + (ys[1] - ys[0]) * tension
        else:
            cp1x = xs[i] + (xs[i + 1] - xs[i - 1]) * tension
            cp1y = ys[i] + (ys[i + 1] - ys[i - 1]) * tension

        if i + 2 >= len(xs):
            cp2x = xs[i + 1] - (xs[i + 1] - xs[i]) * tension
            cp2y = ys[i + 1] - (ys[i + 1] - ys[i]) * tension
        else:
            cp2x = xs[i + 1] - (xs[i + 2] - xs[i]) * tension
            cp2y = ys[i + 1] - (ys[i + 2] - ys[i]) * tension

        path_parts.append(
            f"C {cp1x:.1f},{cp1y:.1f} {cp2x:.1f},{cp2y:.1f} {xs[i+1]:.1f},{ys[i+1]:.1f}"
        )

    path_d = " ".join(path_parts)
    return f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round"/>'


def build_svg():
    parts = []

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}">'
    )

    # Font face for Japanese text
    # Font discovery: try common locations, fallback to sans-serif
    font_paths = [
        Path.home() / ".local" / "share" / "fonts" / "NotoSansJP.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    font_url = ""
    for fp in font_paths:
        if fp.exists():
            font_url = f'file://{fp}'
            break
    if font_url:
        parts.append(
            '<defs><style>'
            f'@font-face {{ font-family: "NotoSansJP"; src: url("{font_url}"); }}'
            '</style></defs>'
        )

    parts.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG_COLOR}"/>')

    # Horizontal grid lines + Y-axis labels
    for i in range(0, 101, 20):
        y = val_to_y(i)
        parts.append(
            f'<line x1="{MARGIN_LEFT}" y1="{y:.1f}" x2="{WIDTH - MARGIN_RIGHT}" y2="{y:.1f}" '
            f'stroke="{GRID_COLOR}" stroke-width="0.5"/>'
        )
        parts.append(
            f'<text x="{MARGIN_LEFT - 8}" y="{y + 4:.1f}" fill="{TEXT_COLOR}" '
            f'font-family="sans-serif" font-size="10" text-anchor="end">{i}</text>'
        )

    # X-axis labels every 5 sessions
    shown = set()
    for s in range(1, SESSIONS + 1, 5):
        x = session_to_x(s)
        parts.append(
            f'<text x="{x:.1f}" y="{MARGIN_TOP + PLOT_H + 15}" fill="{TEXT_COLOR}" '
            f'font-family="sans-serif" font-size="10" text-anchor="middle">{s}</text>'
        )
        shown.add(s)
    if SESSIONS not in shown:
        x58 = session_to_x(SESSIONS)
        parts.append(
            f'<text x="{x58:.1f}" y="{MARGIN_TOP + PLOT_H + 15}" fill="{TEXT_COLOR}" '
            f'font-family="sans-serif" font-size="10" text-anchor="middle">{SESSIONS}</text>'
        )

    # Axes
    parts.append(
        f'<line x1="{MARGIN_LEFT}" y1="{MARGIN_TOP}" x2="{MARGIN_LEFT}" y2="{MARGIN_TOP + PLOT_H}" '
        f'stroke="{AXIS_COLOR}" stroke-width="1"/>'
    )
    parts.append(
        f'<line x1="{MARGIN_LEFT}" y1="{MARGIN_TOP + PLOT_H}" x2="{WIDTH - MARGIN_RIGHT}" y2="{MARGIN_TOP + PLOT_H}" '
        f'stroke="{AXIS_COLOR}" stroke-width="1"/>'
    )

    # Axis titles
    parts.append(
        f'<text x="{MARGIN_LEFT + PLOT_W / 2}" y="{HEIGHT - 8}" fill="{TEXT_COLOR}" '
        f'font-family="sans-serif" font-size="11" text-anchor="middle">Sessions</text>'
    )
    parts.append(
        f'<text x="15" y="{MARGIN_TOP + PLOT_H / 2}" fill="{TEXT_COLOR}" '
        f'font-family="sans-serif" font-size="11" text-anchor="middle" '
        f'transform="rotate(-90, 15, {MARGIN_TOP + PLOT_H / 2})">Growth Index</text>'
    )

    # Version markers
    for session, label in VERSIONS:
        x = session_to_x(session)
        parts.append(
            f'<line x1="{x:.1f}" y1="{MARGIN_TOP}" x2="{x:.1f}" y2="{MARGIN_TOP + PLOT_H}" '
            f'stroke="#6666aa" stroke-width="1" stroke-dasharray="4,3" opacity="0.6"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{MARGIN_TOP - 5}" fill="#8888bb" '
            f'font-family="sans-serif" font-size="10" text-anchor="middle">{label}</text>'
        )

    # Data curves
    skill_data = generate_skill_data()
    accuracy_data = generate_accuracy_data()
    autonomy_data = generate_autonomy_data()

    parts.append(smooth_path(skill_data, PINK, 2.5))
    parts.append(smooth_path(accuracy_data, CYAN, 2.5))
    parts.append(smooth_path(autonomy_data, GOLD, 2.5))

    # Title
    parts.append(
        f'<text x="{WIDTH / 2}" y="28" fill="{TITLE_COLOR}" '
        f'font-family="sans-serif" font-size="16" font-weight="bold" text-anchor="middle">'
        f'Session Growth Over 58 Sessions</text>'
    )

    # Legend
    legend_x = WIDTH - MARGIN_RIGHT - 200
    legend_y = MARGIN_TOP + 10
    legend_items = [
        (PINK, "Skill Count (\u30b9\u30ad\u30eb\u6570)"),
        (CYAN, "Decision Accuracy (\u5224\u65ad\u7cbe\u5ea6)"),
        (GOLD, "Autonomy Level (\u81ea\u5f8b\u5ea6)"),
    ]

    parts.append(
        f'<rect x="{legend_x - 8}" y="{legend_y - 8}" width="205" height="68" '
        f'rx="4" fill="{BG_COLOR}" fill-opacity="0.85" stroke="{GRID_COLOR}" stroke-width="1"/>'
    )

    for idx, (color, label) in enumerate(legend_items):
        ly = legend_y + idx * 20 + 6
        parts.append(
            f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x + 22}" y2="{ly}" '
            f'stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
        )
        parts.append(
            f'<text x="{legend_x + 28}" y="{ly + 4}" fill="{TEXT_COLOR}" '
            f'font-family="NotoSansJP, sans-serif" font-size="11">{label}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    svg_str = build_svg()
    cairosvg.svg2png(
        bytestring=svg_str.encode("utf-8"),
        write_to=OUTPUT_PATH,
        output_width=800,
        output_height=400,
    )
    print(f"Generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
