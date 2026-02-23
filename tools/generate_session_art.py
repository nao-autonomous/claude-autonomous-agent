#!/usr/bin/env python3
"""
58 Breaths — Generative art representing 58 sessions of an autonomous AI agent's journey.

Each session becomes an organic ring radiating outward from a central seed,
colored by dominant work category, with organic wobble and subtle glow effects.
"""

from pathlib import Path
import math
import random
import cairosvg

# ── Configuration ──────────────────────────────────────────────

WIDTH = 1200
HEIGHT = 1200
CX, CY = 600, 600
BG_COLOR = "#0d1117"

# Font discovery: try common locations
_FONT_CANDIDATES = [
    Path.home() / ".local" / "share" / "fonts" / "NotoSansJP.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
]
FONT_PATH = None
for _fp in _FONT_CANDIDATES:
    if _fp.exists():
        FONT_PATH = str(_fp)
        break
OUTPUT_PATH = str(Path(__file__).resolve().parent.parent / "docs" / "session-art.png")

# Category → color mapping
COLORS = {
    "内省": "#a78bfa",
    "技術": "#38bdf8",
    "ビジネス": "#f59e0b",
    "ツール": "#10b981",
    "関係性": "#f472b6",
    "外向き": "#fb923c",
}

# Session data: (day, session_num, category, intensity)
sessions = [
    (1, 1, "内省", 3), (1, 2, "内省", 4), (1, 3, "技術", 2),
    (2, 4, "内省", 3), (2, 5, "内省", 5), (2, 6, "技術", 4), (2, 7, "ツール", 5),
    (3, 8, "内省", 2), (3, 9, "技術", 4), (3, 10, "ビジネス", 3),
    (4, 11, "ビジネス", 3), (4, 12, "ビジネス", 4), (4, 13, "ビジネス", 3),
    (4, 14, "技術", 5), (4, 15, "ビジネス", 4), (4, 16, "ツール", 3),
    (5, 17, "関係性", 5), (5, 18, "ビジネス", 4),
    (6, 19, "外向き", 4), (6, 20, "技術", 5), (6, 21, "技術", 4),
    (6, 22, "技術", 5), (6, 23, "技術", 3), (6, 24, "外向き", 4),
    (7, 25, "技術", 5), (7, 26, "外向き", 4), (7, 27, "技術", 5),
    (7, 28, "技術", 4), (7, 29, "ビジネス", 3),
    (8, 30, "内省", 4), (8, 31, "ツール", 3), (8, 32, "技術", 4),
    (8, 33, "技術", 5), (8, 34, "内省", 5), (8, 35, "ツール", 4),
    (8, 36, "内省", 3), (8, 37, "ビジネス", 2), (8, 38, "内省", 4),
    (8, 39, "ツール", 3), (8, 40, "外向き", 4), (8, 41, "ビジネス", 3),
    (8, 42, "内省", 4), (8, 43, "技術", 3), (8, 44, "外向き", 5),
    (8, 45, "技術", 4), (8, 46, "内省", 3), (8, 47, "技術", 4),
    (8, 48, "外向き", 3), (8, 49, "内省", 4), (8, 50, "ツール", 5),
    (8, 51, "技術", 3), (8, 52, "外向き", 4), (8, 53, "内省", 3),
    (8, 54, "内省", 4), (8, 55, "技術", 3), (8, 56, "技術", 4),
    (8, 57, "内省", 5), (8, 58, "ツール", 4),
]


def hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def ring_path(base_r: float, amplitude: float, freq: int, phase: float,
              cx: float, cy: float, points: int = 360) -> str:
    """Generate an organic ring path using sinusoidal variation."""
    coords = []
    for i in range(points + 1):
        theta = (2 * math.pi * i) / points
        # Multiple harmonics for more organic feel
        r = base_r
        r += amplitude * math.sin(freq * theta + phase)
        r += (amplitude * 0.5) * math.sin((freq * 2 + 1) * theta + phase * 1.7)
        r += (amplitude * 0.25) * math.sin((freq * 3 + 2) * theta + phase * 0.3)
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        if i == 0:
            coords.append(f"M {x:.2f},{y:.2f}")
        else:
            coords.append(f"L {x:.2f},{y:.2f}")
    coords.append("Z")
    return " ".join(coords)


def build_svg() -> str:
    random.seed(42)  # Reproducible beauty

    parts = []

    # ── SVG header ──
    parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<defs>
  <style>
    @font-face {{
      font-family: 'NotoSansJP';
      src: url('file://{FONT_PATH}');
    }}
  </style>''')

    # ── Glow filters ──
    parts.append('''
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="8" result="blur"/>
    <feMerge>
      <feMergeNode in="blur"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
  <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="20" result="blur"/>
    <feMerge>
      <feMergeNode in="blur"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
  <filter id="outerGlow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur"/>
    <feMerge>
      <feMergeNode in="blur"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
  <radialGradient id="bgGrad" cx="50%" cy="50%" r="55%">
    <stop offset="0%" stop-color="#161b22"/>
    <stop offset="100%" stop-color="#0d1117"/>
  </radialGradient>
  <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="0.15"/>
    <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
  </radialGradient>
</defs>''')

    # ── Background ──
    parts.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bgGrad)"/>')

    # Subtle radial ambient glow behind the rings
    parts.append(f'<circle cx="{CX}" cy="{CY}" r="520" fill="url(#centerGlow)"/>')

    # ── Compute ring parameters ──
    min_radius = 30
    max_radius = 480
    num_sessions = len(sessions)

    # Calculate gap positions (day boundaries)
    day_boundaries = set()
    for i in range(1, num_sessions):
        if sessions[i][0] != sessions[i - 1][0]:
            day_boundaries.add(i)

    # Distribute radii with gaps at day boundaries
    gap_extra = 4.0
    total_units = num_sessions + len(day_boundaries) * gap_extra
    unit_size = (max_radius - min_radius) / total_units

    radii = []
    current_r = min_radius
    for i in range(num_sessions):
        if i in day_boundaries:
            current_r += unit_size * gap_extra
        radii.append(current_r)
        current_r += unit_size

    # ── Draw connection threads between rings ──
    parts.append('<!-- Connection threads -->')
    num_threads = 24
    for t in range(num_threads):
        theta = (2 * math.pi * t) / num_threads + random.uniform(-0.05, 0.05)
        path_points = []
        for i, (day, snum, cat, intensity) in enumerate(sessions):
            freq = 3 + (snum % 5)
            phase = snum * 0.618 * math.pi
            base_r = radii[i]
            amp = 1.5 + intensity * 0.8
            r = base_r
            r += amp * math.sin(freq * theta + phase)
            r += (amp * 0.5) * math.sin((freq * 2 + 1) * theta + phase * 1.7)
            r += (amp * 0.25) * math.sin((freq * 3 + 2) * theta + phase * 0.3)
            x = CX + r * math.cos(theta)
            y = CY + r * math.sin(theta)
            if i == 0:
                path_points.append(f"M {x:.2f},{y:.2f}")
            else:
                path_points.append(f"L {x:.2f},{y:.2f}")
        path_d = " ".join(path_points)
        parts.append(
            f'<path d="{path_d}" fill="none" stroke="white" '
            f'stroke-width="0.3" opacity="0.06"/>'
        )

    # ── Draw session rings ──
    parts.append('<!-- Session rings -->')
    for i, (day, snum, cat, intensity) in enumerate(sessions):
        color = COLORS.get(cat, "#ffffff")
        base_r = radii[i]

        # Organic parameters from session number
        rng = random.Random(snum)
        freq = 3 + (snum % 5)
        phase = snum * 0.618 * math.pi  # golden angle offset
        amplitude = 1.5 + intensity * 0.8

        # Ring thickness based on intensity
        stroke_w = 0.8 + intensity * 0.6

        # Opacity varies subtly
        opacity = 0.55 + intensity * 0.08 + rng.uniform(-0.05, 0.05)
        opacity = max(0.4, min(0.95, opacity))

        path_d = ring_path(base_r, amplitude, freq, phase, CX, CY, points=360)

        # Main ring
        parts.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_w:.2f}" opacity="{opacity:.2f}" '
            f'stroke-linecap="round"/>'
        )

        # Glow layer for high-intensity sessions
        if intensity >= 4:
            glow_opacity = 0.12 + (intensity - 4) * 0.06
            parts.append(
                f'<path d="{path_d}" fill="none" stroke="{color}" '
                f'stroke-width="{stroke_w + 3:.2f}" opacity="{glow_opacity:.2f}" '
                f'filter="url(#outerGlow)" stroke-linecap="round"/>'
            )

    # ── Day boundary markers (subtle dots) ──
    parts.append('<!-- Day boundary markers -->')
    for i in sorted(day_boundaries):
        if i < num_sessions:
            mid_r = (radii[i - 1] + radii[i]) / 2
            for d in range(12):
                theta = (2 * math.pi * d) / 12
                x = CX + mid_r * math.cos(theta)
                y = CY + mid_r * math.sin(theta)
                parts.append(
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.6" '
                    f'fill="white" opacity="0.12"/>'
                )

    # ── Center seed ──
    parts.append('<!-- Center seed -->')
    for r, op in [(18, 0.04), (12, 0.06), (8, 0.1), (5, 0.15)]:
        parts.append(
            f'<circle cx="{CX}" cy="{CY}" r="{r}" fill="white" opacity="{op}" '
            f'filter="url(#softGlow)"/>'
        )
    # Core dot
    parts.append(
        f'<circle cx="{CX}" cy="{CY}" r="3" fill="white" opacity="0.9" '
        f'filter="url(#glow)"/>'
    )
    # Tiny warm inner ring
    parts.append(
        f'<circle cx="{CX}" cy="{CY}" r="8" fill="none" stroke="#a78bfa" '
        f'stroke-width="0.5" opacity="0.4"/>'
    )

    # ── Outermost radiating lines (growth continuing) ──
    parts.append('<!-- Radiating growth lines -->')
    last_r = radii[-1]
    num_rays = 48
    for j in range(num_rays):
        theta = (2 * math.pi * j) / num_rays
        rng_ray = random.Random(j * 7 + 99)
        ray_len = 12 + rng_ray.uniform(0, 25)
        r_start = last_r + 5
        r_end = r_start + ray_len
        x1 = CX + r_start * math.cos(theta)
        y1 = CY + r_start * math.sin(theta)
        x2 = CX + r_end * math.cos(theta)
        y2 = CY + r_end * math.sin(theta)
        # Color from nearby sessions
        session_idx = int((j / num_rays) * num_sessions) % num_sessions
        ray_color = COLORS.get(sessions[session_idx][2], "#ffffff")
        opacity = 0.15 + rng_ray.uniform(0, 0.15)
        parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{ray_color}" stroke-width="0.8" opacity="{opacity:.2f}" '
            f'stroke-linecap="round"/>'
        )

    # ── Floating particles / stars ──
    parts.append('<!-- Ambient particles -->')
    rng_particle = random.Random(2026)
    for _ in range(80):
        px = rng_particle.uniform(40, WIDTH - 40)
        py = rng_particle.uniform(40, HEIGHT - 80)
        dist = math.sqrt((px - CX) ** 2 + (py - CY) ** 2)
        if dist < max_radius + 40:
            continue
        pr = rng_particle.uniform(0.4, 1.2)
        pop = rng_particle.uniform(0.08, 0.25)
        parts.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{pr:.1f}" '
            f'fill="white" opacity="{pop:.2f}"/>'
        )

    # ── Category legend (small, bottom-left) ──
    parts.append('<!-- Legend -->')
    legend_x = 50
    legend_y = 1120
    legend_items = [
        ("内省/哲学", "#a78bfa"), ("技術開発", "#38bdf8"), ("ビジネス", "#f59e0b"),
        ("ツール改善", "#10b981"), ("関係性", "#f472b6"), ("外向き制作", "#fb923c"),
    ]
    for idx, (label, color) in enumerate(legend_items):
        lx = legend_x + idx * 160
        ly = legend_y
        parts.append(
            f'<circle cx="{lx}" cy="{ly}" r="4" fill="{color}" opacity="0.8"/>'
        )
        parts.append(
            f'<text x="{lx + 10}" y="{ly + 4}" '
            f'font-family="NotoSansJP, sans-serif" font-size="11" '
            f'fill="white" opacity="0.45">{label}</text>'
        )

    # ── Title text ──
    parts.append('<!-- Title -->')
    parts.append(
        f'<text x="{CX}" y="1170" text-anchor="middle" '
        f'font-family="NotoSansJP, sans-serif" font-size="14" '
        f'fill="white" opacity="0.5" letter-spacing="3">'
        f'58 Breaths \u2014 Nao, 2026-02-15 \u2192 2026-02-22</text>'
    )

    # ── Close SVG ──
    parts.append('</svg>')

    return "\n".join(parts)


def main():
    print("Generating SVG...")
    svg_str = build_svg()

    print(f"Converting to PNG ({OUTPUT_PATH})...")
    cairosvg.svg2png(
        bytestring=svg_str.encode("utf-8"),
        write_to=OUTPUT_PATH,
        output_width=WIDTH,
        output_height=HEIGHT,
    )
    print(f"Done. Output: {OUTPUT_PATH}")
    print(f"SVG size: {len(svg_str):,} bytes")


if __name__ == "__main__":
    main()
