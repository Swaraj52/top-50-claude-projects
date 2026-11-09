"""Tiny server-side SVG charts (bars and lines) with accessible text equivalents."""

from __future__ import annotations

from html import escape

from markupsafe import Markup

W, H, PAD_L, PAD_B, PAD_T = 640, 200, 34, 26, 12


def _frame(title: str, inner: str, labels: list[str]) -> str:
    plot_w = W - PAD_L - 8
    step = plot_w / max(len(labels), 1)
    ticks = "".join(
        f'<text x="{PAD_L + step * i + step / 2:.1f}" y="{H - 8}" class="tick" text-anchor="middle">{escape(lbl)}</text>'
        for i, lbl in enumerate(labels)
    )
    return (
        f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title>{inner}{ticks}</svg>"
    )


def _grid(max_v: float, unit: str) -> str:
    out = []
    for frac in (0, 0.5, 1):
        y = H - PAD_B - (H - PAD_B - PAD_T) * frac
        out.append(f'<line x1="{PAD_L}" x2="{W - 8}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        val = max_v * frac
        out.append(f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" class="tick" text-anchor="end">{val:g}{escape(unit)}</text>')
    return "".join(out)


def bar_chart(title: str, labels: list[str], values: list[float], unit: str = "", highlight_last: bool = True) -> Markup:
    max_v = max(max(values, default=0), 1)
    plot_h = H - PAD_B - PAD_T
    step = (W - PAD_L - 8) / max(len(values), 1)
    bars = []
    for i, v in enumerate(values):
        h = plot_h * (v / max_v)
        x = PAD_L + step * i + step * 0.18
        cls = "bar now" if highlight_last and i == len(values) - 1 else "bar"
        bars.append(
            f'<rect x="{x:.1f}" y="{H - PAD_B - h:.1f}" width="{step * 0.64:.1f}" height="{max(h, 0):.1f}" rx="3" class="{cls}">'
            f"<title>{escape(labels[i])}: {v:g}{escape(unit)}</title></rect>"
        )
    return Markup(_frame(title, _grid(max_v, unit) + "".join(bars), labels))


def line_chart(title: str, labels: list[str], series: list[tuple[str, list[float | None], str]], max_v: float, unit: str = "") -> Markup:
    plot_h = H - PAD_B - PAD_T
    step = (W - PAD_L - 8) / max(len(labels), 1)
    paths = []
    for name, values, cls in series:
        pts = [
            (PAD_L + step * i + step / 2, H - PAD_B - plot_h * (v / max_v))
            for i, v in enumerate(values)
            if v is not None
        ]
        if not pts:
            continue
        d = " ".join(f"{'M' if j == 0 else 'L'}{x:.1f},{y:.1f}" for j, (x, y) in enumerate(pts))
        dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" class="dot {cls}"/>' for x, y in pts)
        paths.append(f'<path d="{d}" class="line {cls}"><title>{escape(name)}</title></path>{dots}')
    return Markup(_frame(title, _grid(max_v, unit) + "".join(paths), labels))
