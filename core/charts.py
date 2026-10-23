"""All Plotly figures in one consistent style (validated categorical palette, thin marks, quiet grid).

Money is plotted in Rs crore (1 Cr = 1e7) so axes stay readable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

CR = 1e7
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
# categorical slots 1..5 in the validated order: blue, orange, aqua, yellow, magenta
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
GOOD, CRIT = "#0ca30c", "#d03b3b"
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def _base(fig: go.Figure, title: str = "", ytitle: str = "", xtitle: str = "", height: int = 380) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, font=dict(size=15, color=INK)),
        height=height, margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=INK2),
        legend=dict(orientation="h", y=-0.18, x=0, font=dict(color=INK2)),
        hoverlabel=dict(bgcolor=SURFACE, font=dict(color=INK, family=FONT), bordercolor=AXIS),
    )
    fig.update_xaxes(title=xtitle, showgrid=False, linecolor=AXIS, tickfont=dict(color=MUTED), zeroline=False)
    fig.update_yaxes(title=ytitle, gridcolor=GRID, gridwidth=1, zeroline=True, zerolinecolor=AXIS,
                     tickfont=dict(color=MUTED), linecolor="rgba(0,0,0,0)")
    return fig


def cr(x):
    return np.asarray(x, dtype=float) / CR


def stacked_compare(parts: dict[str, dict[str, float]]) -> go.Figure:
    """parts = {portfolio label: {component: Rs}} -> stacked bars with a net marker."""
    colors = {"Capex": BLUE, "O&M": ORANGE, "Replacements": AQUA,
              "Residual value": YELLOW, "Energy & water savings": MAGENTA}
    fig = go.Figure()
    labels = list(parts)
    for comp, col in colors.items():
        fig.add_bar(name=comp, x=labels, y=[cr(parts[l][comp]) for l in labels], marker=dict(color=col, line=dict(color=SURFACE, width=2)),
                    hovertemplate=f"{comp}: " + "%{y:.2f} Cr<extra></extra>", width=0.45)
    net = [cr(sum(parts[l].values())) for l in labels]
    fig.add_scatter(x=labels, y=net, mode="markers+text", name="Net LCC",
                    marker=dict(symbol="diamond", size=12, color=INK, line=dict(color=SURFACE, width=2)),
                    text=[f"{v:+.2f} Cr" for v in net], textposition="middle right", textfont=dict(color=INK),
                    hovertemplate="Net LCC: %{y:.2f} Cr<extra></extra>")
    fig.update_layout(barmode="relative")
    return _base(fig, "Life-cycle cost build-up (present worth, vs code-minimum baseline)", "Rs crore", height=430)


def pareto_scatter(df: pd.DataFrame, front: pd.DataFrame, marks: dict[str, tuple[float, float, str]], thresholds: dict[str, float]) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=df["points"], y=cr(df["lcc"]), mode="markers", name="All portfolios",
                    marker=dict(size=6, color=AXIS, opacity=0.6, line=dict(color=SURFACE, width=1)),
                    customdata=df["selection"].map(lambda s: ", ".join(s) or "(none)"),
                    hovertemplate="%{x:g} pts · %{y:.2f} Cr<br>%{customdata}<extra></extra>")
    fig.add_scatter(x=front["points"], y=cr(front["lcc"]), mode="lines+markers", name="Efficient frontier",
                    line=dict(color=BLUE, width=2), marker=dict(size=8, color=BLUE, line=dict(color=SURFACE, width=2)),
                    hovertemplate="%{x:g} pts · %{y:.2f} Cr<extra>Frontier</extra>")
    for name, (x, y, col) in marks.items():
        fig.add_scatter(x=[x], y=[cr(y)], mode="markers", name=name,
                        marker=dict(size=14, color=col, symbol="diamond", line=dict(color=SURFACE, width=2)))
    for lv, pts in thresholds.items():
        fig.add_vline(x=pts, line=dict(color=AXIS, width=1, dash="dot"), annotation_text=lv,
                      annotation_font=dict(color=MUTED, size=11), annotation_position="top")
    return _base(fig, "Every portfolio: IGBC points vs life-cycle cost", "Net LCC (Rs crore, lower is better)", "IGBC points", height=420)


def credit_bars(bd: pd.DataFrame) -> go.Figure:
    d = bd[bd["max"] > 0].iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=d["name"], x=d["max"], orientation="h", name="Maximum", marker=dict(color=GRID), hoverinfo="skip")
    fig.add_bar(y=d["name"], x=d["points"], orientation="h", name="Earned", marker=dict(color=AQUA),
                text=d["points"].map(lambda v: f"{v:g}"), textposition="outside", textfont=dict(color=INK2),
                hovertemplate="%{y}: %{x:g} pts<extra></extra>")
    fig.update_layout(barmode="overlay")
    fig = _base(fig, "Points by credit", "", "Points", height=max(300, 34 * len(d) + 90))
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def upgrade_chart(path: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=path["Level"], y=cr(path["Capex"]), name="Upfront capex", marker=dict(color=BLUE, line=dict(color=SURFACE, width=2)), width=0.35)
    fig.add_bar(x=path["Level"], y=cr(path["LCC"]), name="Net LCC", marker=dict(color=AQUA, line=dict(color=SURFACE, width=2)), width=0.35)
    fig.update_layout(barmode="group")
    return _base(fig, "Cheapest portfolio at each IGBC level", "Rs crore")


def alt_bars(names: list[str], lcc: list[float], eac: list[float]) -> go.Figure:
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Life-cycle cost (present worth)", "Equivalent annual cost"))
    fig.add_bar(x=names, y=cr(lcc), marker=dict(color=BLUE), name="LCC", row=1, col=1, width=0.4,
                text=[f"{v:.2f}" for v in cr(lcc)], textposition="outside", hovertemplate="%{x}: %{y:.2f} Cr<extra></extra>")
    fig.add_bar(x=names, y=np.asarray(eac) / 1e5, marker=dict(color=AQUA), name="EAC", row=1, col=2, width=0.4,
                text=[f"{v:.1f}" for v in np.asarray(eac) / 1e5], textposition="outside", hovertemplate="%{x}: %{y:.1f} L/yr<extra></extra>")
    fig.update_yaxes(title="Rs crore", row=1, col=1)
    fig.update_yaxes(title="Rs lakh per year", row=1, col=2)
    fig.update_layout(showlegend=False)
    fig.for_each_annotation(lambda a: a.update(font=dict(size=13, color=INK2)))
    return _base(fig, "", height=360)


def cumulative_lines(series: dict[str, pd.Series]) -> go.Figure:
    cols = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA]
    fig = go.Figure()
    for (name, s), col in zip(series.items(), cols):
        fig.add_scatter(x=s.index, y=cr(s.values), mode="lines", name=name, line=dict(color=col, width=2),
                        hovertemplate=f"{name}<br>Year %{{x}}: %{{y:.2f}} Cr<extra></extra>")
    fig.add_hline(y=0, line=dict(color=INK2, width=1, dash="dot"))
    return _base(fig, "Cumulative discounted net cost (crossing zero = discounted payback)", "Rs crore", "Year")


def discount_sweep_chart(sw: pd.DataFrame, name_a: str, name_b: str, flip: float | None) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=sw["discount_rate"] * 100, y=cr(sw["lcc_a"]), name=name_a, mode="lines", line=dict(color=ORANGE, width=2),
                    hovertemplate="%{x:.1f}% → %{y:.2f} Cr<extra></extra>")
    fig.add_scatter(x=sw["discount_rate"] * 100, y=cr(sw["lcc_b"]), name=name_b, mode="lines", line=dict(color=BLUE, width=2),
                    hovertemplate="%{x:.1f}% → %{y:.2f} Cr<extra></extra>")
    if flip is not None:
        fig.add_vline(x=flip * 100, line=dict(color=INK2, width=1, dash="dash"),
                      annotation_text=f"rank flips at {flip*100:.1f}%", annotation_font=dict(color=INK2, size=11))
    return _base(fig, "Does the ranking survive a different discount rate?", "Net LCC (Rs crore)", "Discount rate (%)")


def tornado_chart(t: pd.DataFrame) -> go.Figure:
    base = float(t["base"].iloc[0])
    fig = go.Figure()
    fig.add_bar(y=t["parameter"], x=cr(t["worse"]), orientation="h", name="Adverse case", base=0,
                marker=dict(color=ORANGE, line=dict(color=SURFACE, width=2)),
                hovertemplate="%{y}: %{x:+.2f} Cr vs base<extra>Adverse</extra>")
    fig.add_bar(y=t["parameter"], x=cr(t["better"]), orientation="h", name="Favourable case", base=0,
                marker=dict(color=BLUE, line=dict(color=SURFACE, width=2)),
                hovertemplate="%{y}: %{x:+.2f} Cr vs base<extra>Favourable</extra>")
    fig.update_layout(barmode="overlay")
    fig = _base(fig, f"What moves the answer most (base net LCC {base/CR:.2f} Cr)", "", "Change in net LCC (Rs crore)", height=360)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def mc_histogram(a: np.ndarray, b: np.ndarray, name_a: str, name_b: str) -> go.Figure:
    fig = go.Figure()
    for arr, name, col in ((a, name_a, ORANGE), (b, name_b, BLUE)):
        fig.add_histogram(x=cr(arr), name=name, marker=dict(color=col, line=dict(color=SURFACE, width=1)), opacity=0.75, nbinsx=50,
                          hovertemplate="%{x:.2f} Cr: %{y} runs<extra>" + name + "</extra>")
        fig.add_vline(x=float(np.median(cr(arr))), line=dict(color=col, width=2, dash="dash"))
    fig.update_layout(barmode="overlay")
    return _base(fig, "Monte Carlo: spread of net LCC (dashed = median)", "Runs", "Net LCC (Rs crore)")


def macc_chart(df: pd.DataFrame) -> go.Figure:
    """df: name, co2_t, per_t (Rs/tCO2). Width = lifetime tonnes avoided, height = Rs per tonne."""
    d = df.sort_values("per_t")
    fig = go.Figure()
    x0 = 0.0
    for _, r in d.iterrows():
        col = GOOD if r["per_t"] < 0 else CRIT
        fig.add_bar(x=[x0 + r["co2_t"] / 2], y=[r["per_t"]], width=[r["co2_t"] * 0.96], name=r["name"], showlegend=False,
                    marker=dict(color=col, line=dict(color=SURFACE, width=2)), text=[r["name"]], textposition="outside",
                    textfont=dict(size=10, color=INK2),
                    hovertemplate=f"{r['name']}<br>{r['co2_t']:,.0f} t avoided<br>Rs %{{y:,.0f}} per tonne<extra></extra>")
        x0 += r["co2_t"]
    return _base(fig, "Marginal abatement cost: cost (or saving) per tonne of CO2 avoided", "Rs per tCO2 (negative = saves money)", "Lifetime tCO2 avoided (cumulative)", height=400)


def tariff_preview(p0: float, g: float, sd: float, n: int) -> go.Figure:
    t = np.arange(1, n + 1)
    mid = p0 * (1 + g) ** (t - 1)
    lo, hi = p0 * (1 + max(g - sd, -0.02)) ** (t - 1), p0 * (1 + g + sd) ** (t - 1)
    fig = go.Figure()
    fig.add_scatter(x=t, y=hi, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=t, y=lo, mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(42,120,214,0.15)", name="±1 sd band", hoverinfo="skip")
    fig.add_scatter(x=t, y=mid, mode="lines", name="Expected tariff", line=dict(color=BLUE, width=2),
                    hovertemplate="Year %{x}: Rs %{y:.1f}/kWh<extra></extra>")
    return _base(fig, "Grid tariff path used in the model", "Rs per kWh", "Year", height=300)
