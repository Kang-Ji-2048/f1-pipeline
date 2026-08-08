"""Shared visual theme for the dashboard charts.

Centralises the categorical palette and a single ``style_fig`` helper so every
Plotly figure shares the same recessive grid, system font, transparent surface
(so it inherits Streamlit's light/dark background) and colour order. The palette
is the data-viz reference categorical set, validated colourblind-safe.
"""

from __future__ import annotations

import plotly.graph_objects as go

# Categorical palette (data-viz reference order; CVD-validated, fixed order).
PALETTE: list[str] = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]

ACCENT = PALETTE[0]
MUTED = "#898781"  # axis/label ink — reads on both light and dark surfaces
GRID = "rgba(137,135,129,0.22)"  # hairline grid, theme-neutral
FADED = "rgba(137,135,129,0.45)"  # de-emphasised (non-highlighted) series

FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'


def style_fig(fig: go.Figure, *, height: int = 420, show_legend: bool = True) -> go.Figure:
    """Apply the shared look to a Plotly figure and return it."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY, color=MUTED, size=13),
        title=dict(font=dict(size=16, color=MUTED), x=0, xanchor="left"),
        margin=dict(l=8, r=16, t=52, b=8),
        height=height,
        colorway=PALETTE,
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            title_text="",
        ),
        hoverlabel=dict(font_family=FONT_FAMILY),
    )
    fig.update_xaxes(
        showgrid=False, zeroline=False, linecolor=GRID, ticks="outside", tickcolor=GRID
    )
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)")
    return fig
