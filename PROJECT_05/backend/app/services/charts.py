"""Tiny server-rendered bar charts: plain HTML/CSS, no JavaScript or chart library."""

from __future__ import annotations

from markupsafe import Markup, escape


def _number(value: float) -> str:
    return f"{value:g}"


def bar_chart(
    labels: list[str],
    values: list[float | None],
    *,
    title: str,
    unit: str = "",
    height: int = 150,
    label_every: int = 1,
) -> Markup:
    top = max([v for v in values if v is not None] or [0])
    cols = []
    for i, value in enumerate(values):
        v = 0 if value is None else value
        h = 0 if not top else max(0.0, min(100.0, v / top * 100))
        label = labels[i] if i < len(labels) else ""
        show = i % max(1, label_every) == 0 or i == len(values) - 1
        cols.append(
            '<div class="bar-col">'
            f'<span class="bar-value">{_number(v)}{escape(unit)}</span>'
            f'<span class="bar" style="height: {h:.1f}%"></span>'
            f'<span class="bar-label">{"&nbsp;" if show and label == "" else (escape(label) if show else "&nbsp;")}</span>'
            "</div>"
        )
    note = f'<p class="chart-note">Peak: {_number(top)}{escape(unit)}</p>' if unit else ""
    return Markup(
        f'<div class="bars" style="height: {int(height)}px" role="img" aria-label="{escape(title)}">'
        f'{"".join(cols)}</div>{note}'
    )
