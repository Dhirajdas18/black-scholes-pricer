"""Topic reports: build charts into out/ and return the key numbers quoted in the README."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from bsp import plots
from bsp.bs import bs_price, mc_price
from bsp.data import INDEX, VIX, load

RF = 0.065  # assumed risk-free rate (India 91-day T-bills ran roughly 3-7% over 2013-2026)
MONTH_DAYS = 21  # trading days in the option's life
T_MONTH = 30 / 365  # the same month in calendar time, as option pricing uses


def nifty_and_vix() -> pd.DataFrame:
    s = load("adj_close", [INDEX])[INDEX]
    vix = load("close", [VIX])[VIX].reindex(s.index).ffill() / 100
    return pd.DataFrame({"S": s, "vix": vix})


def insurance_table(d: pd.DataFrame, horizon: int = MONTH_DAYS, t: float = T_MONTH,
                    r: float = RF) -> pd.DataFrame:
    """One-month at-the-money options priced by Black-Scholes at India VIX vs what they paid.

    Premiums and payoffs are fractions of the index level on the day the option is bought.
    """
    x = d.assign(ST=d["S"].shift(-horizon)).dropna()
    s, v = x["S"].to_numpy(), x["vix"].to_numpy()
    out = pd.DataFrame(index=x.index)
    out["put"] = bs_price(s, s, t, r, v, "put") / s
    out["call"] = bs_price(s, s, t, r, v, "call") / s
    out["put pays"] = np.maximum(x["S"] - x["ST"], 0) / x["S"]
    out["call pays"] = np.maximum(x["ST"] - x["S"], 0) / x["S"]
    disc = np.exp(-r * t)
    out["put seller"] = out["put"] - disc * out["put pays"]
    out["call seller"] = out["call"] - disc * out["call pays"]
    return out


def report_pricing(out_dir: Path) -> dict:
    """Black-Scholes checked by Monte Carlo; what NIFTY insurance cost vs what it paid."""
    s0, k, t, v, q = 100.0, 105.0, 0.5, 0.22, 0.0
    exact = bs_price(s0, k, t, RF, v, "put", q)
    ns = np.unique(np.logspace(2.5, 6, 15).astype(int) // 2 * 2)
    est = np.array([mc_price(s0, k, t, RF, v, "put", q, n, seed=7) for n in ns])
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.fill_between(ns, est[:, 0] - 2 * est[:, 1], est[:, 0] + 2 * est[:, 1],
                    color=plots.BLUE_RAMP[0], lw=0)
    ax.plot(ns, est[:, 0], "o-", color=plots.SERIES[0], ms=4)
    ax.axhline(exact, color=plots.TEXT, lw=1.2, ls="--")
    ax.annotate(f"Black-Scholes formula: {exact:.3f}", (ns[0], exact), xytext=(0, 6),
                textcoords="offset points", color=plots.TEXT_2, fontsize=9)
    ax.set_xscale("log")
    ax.set_xlabel("simulated paths")
    ax.set_ylabel("put price (spot 100, strike 105, 6 months)")
    ax.set_title("Monte Carlo converges on the formula; the band is ±2 standard errors")
    plots.save(fig, out_dir, "pricing_mc")

    d = nifty_and_vix()
    tab = insurance_table(d)
    runs = [tab.iloc[o::MONTH_DAYS] for o in range(MONTH_DAYS)]
    med = {c: float(np.median([x[c].mean() for x in runs])) for c in tab.columns}
    seller = [x["put seller"].mean() for x in runs]
    x0 = runs[0]

    fig, ax = plt.subplots(figsize=(9, 4.6))
    groups = ["put", "call"]
    w = 0.36
    for i, g in enumerate(groups):
        ax.bar(i - w / 2, med[g] * 100, w, color=plots.SERIES[0],
               label="premium (Black-Scholes at India VIX)" if i == 0 else None)
        ax.bar(i + w / 2, med[f"{g} pays"] * 100, w, color=plots.MUTED,
               label="average payout at expiry" if i == 0 else None)
        for dx, val in ((-w / 2, med[g]), (w / 2, med[f"{g} pays"])):
            ax.text(i + dx, val * 100 + 0.03, f"{val:.2%}", ha="center", fontsize=9,
                    color=plots.TEXT)
    ax.set_xticks(range(2), ["1-month at-the-money put", "1-month at-the-money call"])
    ax.set_ylabel("% of NIFTY")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")
    ax.set_title("NIFTY puts cost more than they paid out; calls were about fair")
    plots.save(fig, out_dir, "pricing_insurance")

    cum = x0["put seller"].cumsum() * 100
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(cum.index, cum, color=plots.SERIES[7], lw=2)
    worst = x0["put pays"].idxmax()
    ax.annotate(f"month from {worst:%d %b %Y}: put paid {x0.loc[worst, 'put pays']:.0%}, "
                f"premium {x0.loc[worst, 'put']:.1%}", (worst, cum.loc[worst]),
                xytext=(10, -20), textcoords="offset points", fontsize=9, color=plots.TEXT_2,
                arrowprops=dict(arrowstyle="-", color=plots.MUTED))
    ax.axhline(0, color=plots.TEXT_2, lw=0.8)
    ax.set_ylabel("cumulative seller profit, % of NIFTY per month")
    ax.set_title("Selling NIFTY puts: small steady gains, then one month takes years back")
    plots.save(fig, out_dir, "pricing_seller")

    return {
        "MC vs formula at 1M paths": f"{est[-1, 0]:.4f} ± {est[-1, 1]:.4f} vs {exact:.4f}",
        "median across 21 start days": {k: round(v, 4) for k, v in med.items()},
        "put seller per month, range across start days": f"{min(seller):.2%} to {max(seller):.2%}",
        "months per start day": len(x0),
        "put finished in the money":
            f"{float(np.median([(x['put pays'] > 0).mean() for x in runs])):.0%}",
        "worst month (start day 0)": f"{worst:%Y-%m-%d}: paid {x0.loc[worst, 'put pays']:.1%}, "
                                     f"premium {x0.loc[worst, 'put']:.2%}",
    }


REPORTS = {"pricing": report_pricing}
