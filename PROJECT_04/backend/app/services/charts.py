"""Tiny server-rendered charts. No JavaScript and no chart library.

Bars are plain HTML/CSS (so labels stay crisp at any width). The line chart
uses an SVG path with a percentage viewBox plus HTML dots and labels, which
keeps text and dot shapes undistorted when the container resizes.
"""

from __future__ import annotations

from markupsafe import Markup, escape


def _number(value: float) -> str:
    return f"{value:g}"


def bar_chart(labels: list[str], values: list[float | None], *, title: str, unit: str = "", height: int = 150) -> Markup:
    top = max([v for v in values if v is not None] or [0])
    cols = []
    for i, value in enumerate(values):
        v = 0 if value is None else value
        h = 0 if not top else max(0.0, min(100.0, v / top * 100))
        label = labels[i] if i < len(labels) else ""
        cols.append(
            '<div class="bar-col">'
            f'<span class="bar-value">{_number(v)}{escape(unit)}</span>'
            f'<span class="bar" style="height: {h:.1f}%"></span>'
            f'<span class="bar-label">{escape(label)}</span>'
            "</div>"
        )
    note = f'<p class="chart-note">Peak: {_number(top)}{escape(unit)}</p>' if unit else ""
    return Markup(
        f'<div class="bars" style="height: {int(height)}px" role="img" aria-label="{escape(title)}">'
        f'{"".join(cols)}</div>{note}'
    )


def line_chart(labels: list[str], values: list[float | None], *, title: str, max_v: float = 5.0, min_v: float = 1.0) -> Markup:
    n = max(1, len(values))
    pad_x, pad_y = 2.0, 8.0  # percent insets so dots never clip
    span = max_v - min_v or 1

    points: list[tuple[int, float, float]] = []
    for i, value in enumerate(values):
        if value is None:
            continue
        x = pad_x + (100 - pad_x * 2) * i / max(1, n - 1)
        clamped = max(min_v, min(max_v, value))
        y = pad_y + (100 - pad_y * 2) * (1 - (clamped - min_v) / span)
        points.append((i, x, y))

    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (_, x, y) in enumerate(points))
    grid = "".join(
        f'<line x1="0" y1="{pad_y + (100 - pad_y * 2) * i / 4:.2f}" x2="100" '
        f'y2="{pad_y + (100 - pad_y * 2) * i / 4:.2f}" class="grid"/>'
        for i in range(5)
    )
    dots = "".join(
        f'<span class="ldot" style="left: {x:.2f}%; top: {y:.2f}%" title="{escape(labels[i]) if i < len(labels) else ""}"></span>'
        for i, x, y in points
    )
    step = max(1, n // 6)
    cells = "".join(
        f'<span>{escape(labels[i]) if i < len(labels) and (i % step == 0 or i == n - 1) else "&nbsp;"}</span>'
        for i in range(n)
    )
    return Markup(
        f'<div class="lineplot" role="img" aria-label="{escape(title)}">'
        f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">{grid}'
        f'<path d="{path}" class="line" vector-effect="non-scaling-stroke"/></svg>'
        f"{dots}</div>"
        f'<div class="line-labels" style="grid-template-columns: repeat({n}, 1fr)">{cells}</div>'
    )
