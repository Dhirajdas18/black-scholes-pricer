"""Interactive dashboard: a live Black-Scholes calculator plus charts, as one static page."""

import json
import re
from pathlib import Path
from string import Template

import pandas as pd
import plotly.graph_objects as go

from bsp import plots

FONT = "system-ui, -apple-system, \"Segoe UI\", Roboto, sans-serif"

ICON = (
    "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 16%22%3E"
    "%3Cpath d=%22M1 12 5 7l3 3 7-8%22 fill=%22none%22 stroke=%22%232a78d6%22"
    " stroke-width=%222%22/%3E"
    "%3C/svg%3E"
)

def _layout(fig: go.Figure, ytitle: str) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=plots.SURFACE,
        plot_bgcolor=plots.SURFACE,
        font=dict(family=FONT, color=plots.TEXT_2, size=13),
        hovermode="x unified",
        margin=dict(l=56, r=24, t=96, b=40),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, xanchor="left"),
        yaxis=dict(title=ytitle, gridcolor=plots.GRID, zeroline=False, automargin=True),
        xaxis=dict(
            gridcolor=plots.GRID,
            rangeslider=dict(visible=False),
            rangeselector=dict(
                buttons=[dict(count=n, label=f"{n}y", step="year", stepmode="backward")
                         for n in (1, 3, 5)] + [dict(step="all", label="All")],
                x=1, xanchor="right", y=1.08, yanchor="bottom", bgcolor="white",
            ),
        ),
    )
    end = max(pd.Timestamp(max(t.x)) for t in fig.data)
    fig.update_xaxes(range=[end - pd.DateOffset(years=3), end])  # open on the last 3 years
    return fig



JS_PRICER = Path(__file__).with_name("pricer.js")

CALCULATOR = (Path(__file__).with_name("calculator.html")).read_text(encoding="utf-8")


def calculator_section(_data) -> str:
    return Template(CALCULATOR).safe_substitute(js=JS_PRICER.read_text(encoding="utf-8"))


def seller_figure(data) -> go.Figure:
    """Cumulative profit of selling a one-month at-the-money NIFTY put each month."""
    from bsp.reports import MONTH_DAYS, insurance_table

    tab = insurance_table(data).iloc[::MONTH_DAYS]
    fig = go.Figure()
    cum = tab["put seller"].cumsum() * 100
    fig.add_scatter(x=list(cum.index.strftime("%Y-%m-%d")), y=cum.round(2).tolist(),
                    name="put seller", line=dict(color=plots.SERIES[7], width=2),
                    hovertemplate="%{y:.1f}% of NIFTY")
    cum_c = tab["call seller"].cumsum() * 100
    fig.add_scatter(x=list(cum_c.index.strftime("%Y-%m-%d")), y=cum_c.round(2).tolist(),
                    name="call seller", line=dict(color=plots.SERIES[0], width=2),
                    hovertemplate="%{y:.1f}% of NIFTY")
    fig = _layout(fig, "cumulative seller profit, % of NIFTY")
    fig.update_xaxes(range=None)
    return fig


def breakeven_figure(data) -> go.Figure:
    """Each day's NIFTY move divided by the break-even move India VIX implied the evening before."""
    from bsp.reports import breakeven_table

    be = breakeven_table(data)
    fig = go.Figure()
    fig.add_scatter(x=list(be.index.strftime("%Y-%m-%d")), y=be["ratio"].round(2).tolist(),
                    mode="markers", name="|move| ÷ break-even",
                    marker=dict(size=3, color=plots.SERIES[0]),
                    hovertemplate="%{x}: %{y:.2f}× the break-even move<extra></extra>")
    fig.add_hline(y=1, line=dict(color=plots.TEXT, width=1, dash="dash"))
    fig = _layout(fig, "daily move ÷ VIX break-even move")
    fig.update_xaxes(range=None)
    return fig


def smile_figure(_data) -> go.Figure:
    """Implied vols at three strikes against what NIFTY then did, from docs/data/nifty_iv.csv."""
    from bsp.reports import IV_SUMMARY

    iv = pd.read_csv(IV_SUMMARY, index_col="date", parse_dates=["date"])
    x = list(iv.index.strftime("%Y-%m-%d"))
    fig = go.Figure()
    lines = [("iv95", "95% put", plots.SERIES[0], "solid"),
             ("iv100", "at the money", plots.SERIES[1], "solid"),
             ("iv105", "105% call", plots.SERIES[2], "solid"),
             ("realised", "what NIFTY then did", plots.TEXT, "dot")]
    for col, name, color, dash in lines:
        fig.add_scatter(x=x, y=(iv[col] * 100).round(1).tolist(), name=name, mode="lines",
                        line=dict(color=color, width=2, dash=dash),
                        hovertemplate=f"{name}: %{{y:.1f}}%<extra></extra>")
    fig = _layout(fig, "volatility, % a year")
    fig.update_layout(hovermode="x unified")
    return fig


def hedge_figure(data) -> go.Figure:
    """Cumulative P&L of selling the monthly at-the-money call, hedged vs unhedged."""
    from bsp.reports import hedge_table, load_iv

    h = hedge_table(load_iv(), data["S"])
    atm = h[h["leg"] == "atm"].set_index("date")
    x = list(atm.index.strftime("%Y-%m-%d"))
    fig = go.Figure()
    for col, name, color in (("unhedged", "unhedged", plots.MUTED),
                             ("hedged", "delta-hedged daily", plots.SERIES[0])):
        fig.add_scatter(x=x, y=(atm[col].cumsum() * 100).round(2).tolist(), name=name,
                        mode="lines", line=dict(color=color, width=2),
                        hovertemplate=f"{name}: %{{y:.1f}}% of NIFTY<extra></extra>")
    fig = _layout(fig, "cumulative P&L, % of NIFTY")
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(range=None)
    return fig


def carry_figure(_data) -> go.Figure:
    """Carry implied by NIFTY futures each month, from docs/data/nifty_black76.csv."""
    from bsp.reports import CARRY, RF

    c = pd.read_csv(CARRY, index_col="date", parse_dates=["date"])
    x = list(c.index.strftime("%Y-%m-%d"))
    fig = go.Figure()
    fig.add_scatter(x=x, y=(c["carry"] * 100).round(2).tolist(), name="futures carry",
                    mode="lines+markers", line=dict(color=plots.SERIES[0], width=2),
                    marker=dict(size=4),
                    hovertemplate="carry %{y:.1f}% a year<extra></extra>")
    fig.add_hline(y=RF * 100, line=dict(color=plots.MUTED, width=1, dash="dash"))
    fig = _layout(fig, "ln(futures / spot) / T, % a year")
    fig.update_xaxes(range=None)
    return fig


SECTIONS = [
    ("Option calculator",
     "European option prices and Greeks from the Black-Scholes formula, computed in your browser "
     "as you type. Volatility is the one input you can't observe: the rest of this page is about "
     "it.",
     calculator_section),
    ("What NIFTY insurance cost",
     "Each month, a one-month at-the-money NIFTY option priced by Black-Scholes at that day's "
     "India VIX, then held to expiry. The lines add up what an option seller kept each month, "
     "before costs. Puts cost more than they paid out on average; calls were about fair.",
     seller_figure),
    ("Gamma against theta",
     "An at-the-money option holder gains from big moves (gamma) and pays time decay (theta) every "
     "day; the two cancel when NIFTY moves India VIX ÷ √252 in a day. Dots above the dashed line "
     "are days the holder won. NIFTY cleared the line on only 22% of days, against 32% for a bell "
     "curve, but its biggest jumps were bigger than a bell curve allows.",
     breakeven_figure),
    ("The volatility smile",
     "Implied volatility backed out of real NIFTY option closing prices on the first trading day "
     "of each month, about four weeks to expiry. Black-Scholes says all three lines should be "
     "the same; the 95% put sat 4.4 points above the 105% call in the median month and above it "
     "in every month since 2015. The dotted line is the volatility NIFTY actually showed until "
     "expiry.",
     smile_figure),
    ("Delta hedging",
     "Each month, sell the at-the-money NIFTY call at its real implied volatility and hold delta "
     "units of NIFTY, rebalanced daily, until expiry (before trading costs). Unhedged, the result "
     "follows the market; hedged, it follows the gap between implied and realised volatility, "
     "with a sixth of the risk.",
     hedge_figure),
    ("Futures and Black-76",
     "Black-76 prices an option off the futures price, which already contains interest minus "
     "dividends, so no dividend guess is needed (enter a futures price in the calculator to use "
     "it). NIFTY futures carried a median 4.4% a year against the 6.5% rate assumed elsewhere, "
     "and less in the June–August dividend season. The dashed line is 6.5%.",
     carry_figure),
]

REPO = "https://github.com/Dhirajdas18/black-scholes-pricer"
PAGE = Template((Path(__file__).with_name("page.html")).read_text(encoding="utf-8"))


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def build_html(data: pd.DataFrame) -> str:
    parts, nav, loaded = [], [], False
    for title, blurb, make in SECTIONS:
        out = make(data)
        if isinstance(out, str):
            body = out
        else:
            body = out.to_html(full_html=False, include_plotlyjs=False if loaded else "cdn",
                               config={"displaylogo": False, "responsive": True})
            loaded = True
        sid = _slug(title)
        nav.append(f'<li><a href="#{sid}">{title}</a></li>')
        parts.append(f'<section id="{sid}">\n<h2>{title}</h2>\n<p>{blurb}</p>\n{body}\n</section>')
    if not loaded:  # the page script expects Plotly
        parts.append('<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>')
    return PAGE.substitute(
        icon=ICON, font=FONT, repo=REPO, updated=f"{data.index[-1]:%d %b %Y}",
        surface=plots.SURFACE, text=plots.TEXT, text2=plots.TEXT_2, grid=plots.GRID,
        accent=plots.SERIES[0], d_surface=plots.DARK[plots.SURFACE], d_text=plots.DARK[plots.TEXT],
        d_text2=plots.DARK[plots.TEXT_2], d_grid=plots.DARK[plots.GRID],
        d_accent=plots.DARK[plots.SERIES[0]],
        dark=json.dumps({k.lower(): v for k, v in plots.DARK.items()}),
        dark_lines=json.dumps({k.lower(): v for k, v in plots.DARK_LINES.items()}),
        nav="\n".join(nav), sections="\n".join(parts),
    )
