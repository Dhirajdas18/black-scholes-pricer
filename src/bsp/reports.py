"""Topic reports: build charts into out/ and return the key numbers quoted in the README."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

from bsp import plots
from bsp.bs import bs_price, mc_price
from bsp.costs import RATES, RATES_PRE_2026, futures_cost, option_cost
from bsp.data import INDEX, VIX, load
from bsp.greeks import greeks
from bsp.hedge import delta_hedge

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


def breakeven_table(d: pd.DataFrame) -> pd.DataFrame:
    """Each day's NIFTY move against the break-even move India VIX implied the evening before.

    For an at-the-money option, gamma gains and theta losses cancel when the day's move equals
    sigma / sqrt(252) of spot (trading-day convention). `pnl` is the long-gamma profit in those
    units: 0.5 * (move^2 - breakeven^2).
    """
    r = np.log(d["S"] / d["S"].shift(1))
    be = d["vix"].shift(1) / np.sqrt(252)
    x = pd.concat([r, be], axis=1, keys=["move", "breakeven"]).dropna()
    x["ratio"] = x["move"].abs() / x["breakeven"]
    x["pnl"] = 0.5 * (x["move"] ** 2 - x["breakeven"] ** 2)
    return x


def taylor_errors(d: pd.DataFrame) -> pd.Series:
    """Error of delta + gamma + theta in predicting a day's change in a 30-day at-the-money call
    (volatility held at the previous VIX), as a fraction of the option's price."""
    s0, s1, v = d["S"].shift(1), d["S"], d["vix"].shift(1)
    ok = s0.notna() & v.notna()
    s0, s1, v = s0[ok].to_numpy(), s1[ok].to_numpy(), v[ok].to_numpy()
    t = 30 / 365
    c0 = bs_price(s0, s0, t, RF, v, "call")
    c1 = bs_price(s1, s0, t - 1 / 365, RF, v, "call")
    g = greeks(s0, s0, t, RF, v, "call")
    ds = s1 - s0
    approx = g["delta"] * ds + 0.5 * g["gamma"] * ds**2 + g["theta"]
    return pd.Series((approx - (c1 - c0)) / c0, index=d.index[ok])


def report_greeks(out_dir: Path) -> dict:
    """How the Greeks behave, and the daily gamma-vs-theta race on real NIFTY moves."""
    spot = np.linspace(22500, 27500, 400)
    k, v = 25000.0, 0.15
    tenors = {"30 days": (30, plots.BLUE_RAMP[2]), "7 days": (7, plots.BLUE_RAMP[4]),
              "1 day": (1, plots.BLUE_RAMP[6])}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 4.6))
    for name, (days, color) in tenors.items():
        g = greeks(spot, k, days / 365, RF, v, "call")
        a1.plot(spot, g["delta"], color=color, label=name)
        a2.plot(spot, g["gamma"] * 1000, color=color, label=name)
    a1.set_title("delta (call)", fontsize=10, fontweight="normal", color=plots.TEXT_2)
    a2.set_title("gamma, per ₹1,000 move", fontsize=10, fontweight="normal", color=plots.TEXT_2)
    for a in (a1, a2):
        a.axvline(k, color=plots.MUTED, lw=0.8, ls="--")
        a.set_xlabel("NIFTY level (strike 25,000)")
    a2.legend(loc="upper right")
    fig.suptitle("Near expiry, delta becomes a switch and gamma a spike at the strike", x=0.06,
                 ha="left", fontsize=13, fontweight="semibold", color=plots.TEXT)
    plots.save(fig, out_dir, "greeks_curves")

    days = np.arange(30, -0.01, -0.25)
    value = bs_price(25000.0, k, days / 365, RF, v, "call")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(days, value, color=plots.SERIES[0])
    ax.invert_xaxis()
    half = days[np.argmin(np.abs(value - value[0] / 2))]
    ax.axhline(value[0] / 2, color=plots.MUTED, lw=0.8, ls="--")
    ax.annotate(f"half the value is gone with {half:.0f} days still left", (half, value[0] / 2),
                xytext=(-8, 8), textcoords="offset points", color=plots.TEXT_2, fontsize=9,
                ha="right")
    ax.set_xlabel("days to expiry")
    ax.set_ylabel("₹ value of an at-the-money call")
    ax.set_title("Time decay (theta) speeds up into expiry: value falls with √(time left)")
    plots.save(fig, out_dir, "greeks_theta")

    d = nifty_and_vix()
    be = breakeven_table(d)
    normal = {k: float(2 * norm.sf(k)) for k in (1, 2, 3)}
    actual = {k: float((be["ratio"] > k).mean()) for k in (1, 2, 3)}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    xs = np.arange(3)
    ax.bar(xs - 0.2, [actual[k] * 100 for k in (1, 2, 3)], 0.38, color=plots.SERIES[0],
           label="NIFTY 2013–2026")
    ax.bar(xs + 0.2, [normal[k] * 100 for k in (1, 2, 3)], 0.38, color=plots.MUTED,
           label="bell curve at the same volatility")
    for i, kk in enumerate((1, 2, 3)):
        ax.text(i - 0.2, actual[kk] * 100, f"{actual[kk]:.2%}", ha="center", va="bottom",
                fontsize=9)
        ax.text(i + 0.2, normal[kk] * 100, f"{normal[kk]:.2%}", ha="center", va="bottom",
                fontsize=9, color=plots.TEXT_2)
    ax.set_yscale("log")
    ax.set_xticks(xs, ["beyond break-even", "beyond 2×", "beyond 3×"])
    ax.set_ylabel("share of days, % (log scale)")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    ax.set_title("NIFTY beat VIX's break-even move less often than a bell curve, except in jumps")
    plots.save(fig, out_dir, "greeks_breakeven")

    top = be["pnl"].sort_values(ascending=False)
    n1 = int(len(top) * 0.01)
    err = taylor_errors(d)
    moves = be["move"].abs().reindex(err.index)
    return {
        "days": len(be),
        "share beyond break-even (actual vs normal)":
            {k: (round(actual[k], 4), round(normal[k], 4)) for k in (1, 2, 3)},
        "long-gamma pnl: total / top 1% days / the rest":
            (round(float(top.sum()), 4), round(float(top.iloc[:n1].sum()), 4),
             round(float(top.iloc[n1:].sum()), 4)),
        "half of a 30-day ATM call's value gone with days left": round(float(half), 1),
        "delta-gamma-theta error, median": f"{err.abs().median():.2%}",
        "error on days NIFTY moved > 3%": f"{err[moves > 0.03].abs().median():.2%}",
        "worst error": f"{err.abs().idxmax():%Y-%m-%d} {err.abs().max():.1%} "
                       f"(NIFTY {be['move'].loc[err.abs().idxmax()]:+.1%})",
    }


OPTIONS = Path("data/options/nifty_options.parquet")  # local only: scripts/fetch_options.py
IV_SUMMARY = Path("docs/data/nifty_iv.csv")  # derived implied vols only, committed for the site
GRID = np.round(np.arange(0.88, 1.1201, 0.01), 2)


def realised_vol(s: pd.Series, start, end) -> float:
    """Annualised volatility of daily log returns from `start` to `end` (both included)."""
    r = np.log(s[(s.index >= start) & (s.index <= end)]).diff().dropna()
    return float(np.sqrt((r**2).mean() * 252)) if len(r) > 3 else float("nan")


def iv_tables(options: pd.DataFrame, s: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per snapshot: implied vols at fixed moneyness plus the realised vol over the option's
    life (summary), and each snapshot's smile interpolated onto GRID (rows: dates)."""
    from bsp.iv import snapshot_smile

    rows, grid = [], {}
    for day, chain in options.groupby("date"):
        res = snapshot_smile(chain, day, RF)
        if res is None:
            continue
        summary, otm = res
        summary["realised"] = realised_vol(s, day, summary["expiry"])
        rows.append(summary)
        m, iv = otm["moneyness"].to_numpy(), otm["iv"].to_numpy()
        grid[day] = np.where((GRID >= m.min()) & (GRID <= m.max()), np.interp(GRID, m, iv),
                             np.nan)
    return pd.DataFrame(rows).set_index("date"), pd.DataFrame(grid, index=GRID).T


def report_iv(out_dir: Path) -> dict:
    """Implied volatility backed out of real NIFTY option prices: the smile and its premium."""
    summary, grid = iv_tables(pd.read_parquet(OPTIONS), nifty_and_vix()["S"])
    IV_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    cols = ["expiry", "days", "forward", "iv90", "iv95", "iv100", "iv105", "iv110", "realised"]
    summary[cols].to_csv(IV_SUMMARY, float_format="%.4f")

    med, lo, hi = (grid.quantile(q) * 100 for q in (0.5, 0.25, 0.75))
    atm = float(med.loc[1.0])
    fig, ax = plt.subplots(figsize=(9, 4.6))
    x = GRID * 100
    ax.fill_between(x, lo, hi, color=plots.SERIES[0], alpha=0.15, lw=0,
                    label="middle half of months")
    ax.plot(x, med, color=plots.SERIES[0], marker="o", ms=3, label="median month")
    ax.axhline(atm, color=plots.MUTED, lw=1, ls="--", label="Black-Scholes: one volatility")
    ax.axvline(100, color=plots.MUTED, lw=0.8)
    ax.set_xlabel("strike, % of the forward price (puts left of 100, calls right)")
    ax.set_ylabel("implied volatility, %")
    ax.legend(loc="upper center")
    ax.set_title("NIFTY options price a crash as likelier than Black-Scholes allows")
    plots.save(fig, out_dir, "iv_smile")

    keys = {"iv95": "95% put", "iv100": "at the money", "iv105": "105% call"}
    gap = {k: float((summary[k] - summary["realised"]).median() * 100) for k in keys}
    share = {k: float((summary[k] > summary["realised"]).mean()) for k in keys}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    xs = np.arange(len(keys))
    ax.bar(xs, list(gap.values()), 0.55, color=plots.SERIES[0])
    for i, k in enumerate(keys):
        ax.text(i, gap[k], f"+{gap[k]:.1f} pts\nabove in {share[k]:.0%} of months",
                ha="center", va="bottom", fontsize=9, color=plots.TEXT_2)
    ax.set_xticks(xs, list(keys.values()))
    ax.set_ylabel("implied minus realised volatility, pts")
    ax.set_ylim(0, max(gap.values()) * 1.35)
    ax.grid(axis="x", visible=False)
    ax.set_title("The further out-of-the-money the put, the more it overstated what followed")
    plots.save(fig, out_dir, "iv_premium")

    skew = (summary["iv95"] - summary["iv105"]) * 100
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(skew.index, skew, color=plots.SERIES[0], marker="o", ms=3)
    ax.axhline(0, color=plots.MUTED, lw=0.8)
    ax.set_ylabel("95% put minus 105% call implied vol, pts")
    ax.set_ylim(bottom=min(0, skew.min()) - 0.5)
    ax.set_title("The skew never flipped: downside options cost more every month since 2015")
    plots.save(fig, out_dir, "iv_skew")

    crash = summary.loc["2020-03"].iloc[0]
    return {
        "snapshots": len(summary),
        "median iv at 90/95/100/105/110%":
            [round(float(summary[f"iv{k}"].median()) * 100, 1) for k in (90, 95, 100, 105, 110)],
        "skew 95-105, median pts": round(float(skew.median()), 2),
        "skew positive share": round(float((skew > 0).mean()), 3),
        "skew 10%/90% pts": [round(float(v), 1) for v in skew.quantile([0.1, 0.9])],
        "implied minus realised (median pts, share above)":
            {keys[k]: (round(gap[k], 2), round(share[k], 3)) for k in keys},
        "ATM iv minus India VIX, median pts":
            round(float((summary["iv100"] - nifty_and_vix()["vix"].reindex(summary.index,
                                                                           method="ffill"))
                        .median() * 100), 2),
        "2020-03 snapshot (iv95, iv100, realised)":
            tuple(round(float(crash[k]), 3) for k in ("iv95", "iv100", "realised")),
        "widest skew": f"{skew.idxmax():%Y-%m-%d} {skew.max():.1f} pts",
    }


LEGS = {"atm": ("at-the-money call", 1.0, "iv100", "call"),
        "put95": ("95% put", 0.95, "iv95", "put")}


def hedge_table(iv: pd.DataFrame, s: pd.Series, every: int = 1) -> pd.DataFrame:
    """Each month: sell the at-the-money call and the 95% put at their real implied vols and
    delta-hedge with NIFTY until expiry. P&L as a fraction of NIFTY at the sale.

    The dividend yield comes from the options' own forward: q = r - ln(F / S) / T. If the expiry
    was a holiday, the last trading day before it counts as expiry.
    """
    rows = []
    for day, x in iv.iterrows():
        path = s[(s.index >= day) & (s.index <= x["expiry"])]
        if len(path) < 5:
            continue
        t = np.array([(x["expiry"] - d).days / 365 for d in path.index])
        t[-1] = 0.0
        s0, big_t = float(path.iloc[0]), (x["expiry"] - day).days / 365
        q = RF - np.log(x["forward"] / s0) / big_t
        for leg, (_, m, col, kind) in LEGS.items():
            out = delta_hedge(path.to_numpy(), m * x["forward"], t, RF, x[col], kind, q, every)
            rows.append({"date": day, "leg": leg, "hedged": out["pnl"] / s0,
                         "unhedged": out["unhedged"] / s0, "premium": out["premium"] / s0,
                         "gap": x[col] - x["realised"], "spot": s0,
                         "premium_pts": out["premium"], "payoff_pts": out["payoff"],
                         "bought": out["bought"], "sold": out["sold"],
                         "rebalances": out["rebalances"]})
    return pd.DataFrame(rows)


def load_iv() -> pd.DataFrame:
    return pd.read_csv(IV_SUMMARY, parse_dates=["date", "expiry"], index_col="date")


def report_hedging(out_dir: Path) -> dict:
    """Delta hedging: simulated error vs rebalancing frequency, then real NIFTY months."""
    rng = np.random.default_rng(7)
    sigma, steps, t_life = 0.15, 21, 30 / 365
    z = rng.standard_normal((1000, steps))
    dt = t_life / steps
    paths = 25000 * np.exp(np.hstack([np.zeros((1000, 1)), np.cumsum(
        (RF - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z, axis=1)]))
    times = np.linspace(t_life, 0, steps + 1)
    premium = float(bs_price(25000, 25000, t_life, RF, sigma, "call"))
    freq = {1: "daily", 2: "every 2 days", 5: "weekly", 10: "fortnightly", 21: "once, at the sale"}
    err = {e: np.std([delta_hedge(p, 25000, times, RF, sigma, every=e)["pnl"] for p in paths])
           / premium for e in freq}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    xs = np.arange(len(freq))
    ax.bar(xs, [err[e] * 100 for e in freq], 0.55, color=plots.SERIES[0])
    for i, e in enumerate(freq):
        ax.text(i, err[e] * 100, f"{err[e]:.0%}", ha="center", va="bottom", fontsize=9,
                color=plots.TEXT_2)
    ax.set_xticks(xs, list(freq.values()))
    ax.set_ylabel("spread of hedged P&L, % of the premium")
    ax.grid(axis="x", visible=False)
    ax.set_title("Simulated: hedging more often shrinks the error, but never to zero")
    plots.save(fig, out_dir, "hedge_frequency")

    d = nifty_and_vix()
    h = hedge_table(load_iv(), d["S"])
    atm = h[h["leg"] == "atm"].set_index("date")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(atm.index, atm["unhedged"].cumsum() * 100, color=plots.MUTED, label="unhedged")
    ax.plot(atm.index, atm["hedged"].cumsum() * 100, color=plots.SERIES[0],
            label="delta-hedged daily")
    ax.axhline(0, color=plots.MUTED, lw=0.8)
    ax.set_ylabel("cumulative P&L, % of NIFTY (before costs)")
    ax.legend(loc="lower left")
    ax.set_title("Selling a monthly at-the-money NIFTY call: hedged, the profit is steady")
    plots.save(fig, out_dir, "hedge_cumulative")

    fig, ax = plt.subplots(figsize=(9, 4.6))
    for leg, color in (("atm", plots.SERIES[0]), ("put95", plots.SERIES[1])):
        g = h[h["leg"] == leg]
        ax.scatter(g["gap"] * 100, g["hedged"] * 100, s=14, color=color, label=LEGS[leg][0],
                   edgecolor=plots.SURFACE, lw=0.5)
    ax.axhline(0, color=plots.MUTED, lw=0.8)
    ax.axvline(0, color=plots.MUTED, lw=0.8)
    lo = -16
    off = h[h["gap"] * 100 < lo]
    for _, row in off.iterrows():
        ax.annotate(f"{row['date']:%b %Y}: {row['gap'] * 100:.0f} pts ←", (lo, row["hedged"] * 100),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=8,
                    color=plots.TEXT_2)
    ax.set_xlim(lo, h["gap"].max() * 100 + 2)
    ax.set_xlabel("implied minus realised volatility, pts (axis clipped at −16)")
    ax.set_ylabel("hedged seller's P&L, % of NIFTY")
    ax.legend(loc="upper left")
    ax.set_title("Hedged, the seller earns the gap between implied and realised volatility")
    plots.save(fig, out_dir, "hedge_gap")

    weekly = hedge_table(load_iv(), d["S"], every=5)
    out = {"simulated spread, % of premium": {freq[e]: round(err[e] * 100, 1) for e in freq}}
    for leg, (name, *_rest) in LEGS.items():
        g, w = h[h["leg"] == leg], weekly[weekly["leg"] == leg]
        worst = g.loc[g["hedged"].idxmin()]
        out[name] = {
            "months": len(g),
            "premium median %": round(g["premium"].median() * 100, 2),
            "hedged mean / std / win": (round(g["hedged"].mean() * 100, 3),
                                        round(g["hedged"].std() * 100, 3),
                                        round(float((g["hedged"] > 0).mean()), 3)),
            "unhedged mean / std / win": (round(g["unhedged"].mean() * 100, 3),
                                          round(g["unhedged"].std() * 100, 3),
                                          round(float((g["unhedged"] > 0).mean()), 3)),
            "weekly-hedged std": round(w["hedged"].std() * 100, 3),
            "corr(hedged, iv - realised)": round(float(g["hedged"].corr(g["gap"])), 3),
            "worst hedged": f"{worst['date']:%Y-%m-%d} {worst['hedged']:.2%}",
            "worst unhedged": f"{g.loc[g['unhedged'].idxmin(), 'date']:%Y-%m-%d} "
                              f"{g['unhedged'].min():.2%}",
            "2020-03 hedged / unhedged": tuple(
                f"{v:.2%}" for v in g.loc[g["date"] == "2020-03-02", ["hedged", "unhedged"]]
                .iloc[0]),
            "total hedged / unhedged %": (round(g["hedged"].sum() * 100, 1),
                                          round(g["unhedged"].sum() * 100, 1)),
        }
    return out


CARRY = Path("docs/data/nifty_black76.csv")  # derived numbers only, committed for the site


def black76_table(options: pd.DataFrame, iv: pd.DataFrame, s: pd.Series) -> pd.DataFrame:
    """Each month, at the strike nearest the futures price: implied vol of the call and the put
    by Black-76 on the futures price, and by Black-Scholes on spot with no dividends. The two
    should agree for a correct forward. Also the carry the futures price implies, ln(F/S)/T."""
    from bsp.black76 import implied_vol_76
    from bsp.iv import implied_vol

    rows = []
    for day, x in iv.iterrows():
        chain = options[(options["date"] == day) & (options["expiry"] == x["expiry"])]
        f = float(chain.loc[chain["type"] == "FUT", "price"].iloc[0])
        spot, t = float(s.asof(day)), (x["expiry"] - day).days / 365
        pairs = chain[chain["type"] != "FUT"].pivot_table(index="strike", columns="type",
                                                          values="price").dropna()
        k = pairs.index[np.abs(pairs.index - f).argmin()]
        c, p = pairs.loc[k, "CE"], pairs.loc[k, "PE"]
        rows.append({"date": day, "futures": f, "spot": spot,
                     "carry": np.log(f / spot) / t,
                     "b76_call": implied_vol_76(c, f, k, t, RF, "call"),
                     "b76_put": implied_vol_76(p, f, k, t, RF, "put"),
                     "bs_call": implied_vol(c, spot, k, t, RF, "call"),
                     "bs_put": implied_vol(p, spot, k, t, RF, "put")})
    return pd.DataFrame(rows).set_index("date")


def report_black76(out_dir: Path) -> dict:
    """Black-76 on NIFTY futures vs Black-Scholes on spot, and the carry in futures prices."""
    t = black76_table(pd.read_parquet(OPTIONS), load_iv(), nifty_and_vix()["S"])
    t[["carry", "b76_call", "b76_put", "bs_call", "bs_put"]].to_csv(CARRY, float_format="%.5f")
    gap76 = (t["b76_call"] - t["b76_put"]) * 100
    gapbs = (t["bs_call"] - t["bs_put"]) * 100

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(gapbs.index, gapbs, color=plots.MUTED, marker="o", ms=3,
            label="Black-Scholes on spot, no dividends")
    ax.plot(gap76.index, gap76, color=plots.SERIES[0], marker="o", ms=3,
            label="Black-76 on the futures price")
    ax.axhline(0, color=plots.TEXT_2, lw=0.8)
    ax.set_ylabel("call minus put implied vol, same strike, pts")
    ax.legend(loc="lower left")
    ax.set_title("Priced off futures, the call and put agree; off spot, they don't")
    plots.save(fig, out_dir, "b76_gap")

    carry = t["carry"] * 100
    yearly = carry.groupby(carry.index.year).median()
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(carry.index, carry, color=plots.SERIES[0], alpha=0.35, lw=1, label="each month")
    ax.plot(pd.to_datetime([f"{y}-07-01" for y in yearly.index]), yearly.to_numpy(),
            color=plots.SERIES[0], marker="o", label="yearly median")
    ax.axhline(RF * 100, color=plots.MUTED, ls="--", lw=1, label="6.5% rate assumed elsewhere")
    ax.set_ylabel("futures carry, % a year: ln(futures / spot) / T")
    ax.legend(loc="lower left")
    ax.set_title("NIFTY futures carried a median 4.4% a year: interest minus dividends")
    plots.save(fig, out_dir, "b76_carry")

    return {
        "months": len(t),
        "|call - put| iv, median pts (Black-76 / BS spot)":
            (round(float(gap76.abs().median()), 2), round(float(gapbs.abs().median()), 2)),
        "BS spot call - put, median / worst pts":
            (round(float(gapbs.median()), 2), round(float(gapbs.min()), 2)),
        "carry median % / 5-95%": (round(float(carry.median()), 2),
                                   [round(float(v), 1) for v in carry.quantile([0.05, 0.95])]),
        "implied dividend etc. (6.5% - carry), median %": round(RF * 100 - float(carry.median()),
                                                                 2),
        "yearly carry medians %": {int(y): round(float(v), 1) for y, v in yearly.items()},
        "lowest carry month": f"{carry.idxmin():%Y-%m-%d} {carry.min():.1f}%",
    }


BOOK_LOTS = 10  # position size the costs are worked out for: 10 NIFTY lots
HALF_SPREADS = (0.0, 1.0, 2.0)  # assumed index points per option trade (no quotes in the data)


def with_costs(h: pd.DataFrame, half_spread: float = 1.0, rates: dict = RATES) -> pd.DataFrame:
    """Add costs (fractions of NIFTY) to hedge_table rows: selling the option, buying it and
    holding to expiry (exercise STT if it ends in the money), and the futures hedge trades."""
    out = h.copy()
    out["sell_cost"] = [option_cost(p, "sell", BOOK_LOTS, 1, half_spread=half_spread,
                                    rates=rates) for p in h["premium_pts"]] / h["spot"]
    out["buy_cost"] = [option_cost(p, "buy", BOOK_LOTS, 1, intrinsic=y, half_spread=half_spread,
                                   rates=rates)
                       for p, y in zip(h["premium_pts"], h["payoff_pts"], strict=True)] / h["spot"]
    out["hedge_cost"] = [futures_cost(b, sl, orders=int(n) + 1, units=BOOK_LOTS * rates["lot"],
                                      rates=rates)
                         for b, sl, n in zip(h["bought"], h["sold"], h["rebalances"],
                                             strict=True)] / h["spot"]
    out["hedge_stt"] = h["sold"] * rates["stt_fut_sell"] / h["spot"]
    out["hedged_net"] = out["hedged"] - out["sell_cost"] - out["hedge_cost"]
    out["seller_net"] = out["unhedged"] - out["sell_cost"]
    out["buyer_net"] = -out["unhedged"] - out["buy_cost"]
    return out


def report_costs(out_dir: Path) -> dict:
    """What Indian trading costs do to option selling, buying and delta hedging."""
    s, iv = nifty_and_vix()["S"], load_iv()
    freq = {1: "daily", 2: "every 2 days", 5: "weekly"}
    tables = {e: with_costs(hedge_table(iv, s, e)) for e in freq}
    daily = tables[1]
    atm = daily[daily["leg"] == "atm"]
    pct = lambda x: float(x.mean() * 100)  # noqa: E731

    gross, opt = pct(atm["hedged"]), pct(atm["sell_cost"])
    stt, other = pct(atm["hedge_stt"]), pct(atm["hedge_cost"] - atm["hedge_stt"])
    steps = [("gross edge", gross), ("selling the option*", -opt), ("STT on hedge sales", -stt),
             ("other hedge fees", -other)]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    level = 0.0
    for i, (_name, v) in enumerate(steps):
        bottom = level if v >= 0 else level + v
        ax.bar(i, abs(v), 0.55, bottom=bottom,
               color=plots.SERIES[0] if v >= 0 else plots.SERIES[1])
        ax.text(i, level + max(v, 0) + 0.003, f"{v:+.3f}%", ha="center", fontsize=9,
                color=plots.TEXT_2)
        level += v
    ax.bar(len(steps), level, 0.55, color=plots.SERIES[0])
    ax.text(len(steps), level + 0.003, f"{level:.3f}%", ha="center", fontsize=9,
            color=plots.TEXT_2)
    ax.set_xticks(range(len(steps) + 1), [n for n, _ in steps] + ["net"])
    ax.set_ylabel("average per month, % of NIFTY")
    ax.grid(axis="x", visible=False)
    ax.set_title("Daily-hedged at-the-money call seller: hedge trading costs take a quarter")
    ax.annotate("* fees, STT and an assumed 1-point half-spread; 10 lots", (0, 0),
                xycoords="axes fraction", xytext=(0, -32), textcoords="offset points",
                fontsize=8, color=plots.TEXT_2)
    plots.save(fig, out_dir, "costs_waterfall")

    fig, ax = plt.subplots(figsize=(9, 4.6))
    xs = np.arange(len(freq))
    g_atm = [pct(tables[e].query("leg == 'atm'")["hedged"]) for e in freq]
    n_atm = [pct(tables[e].query("leg == 'atm'")["hedged_net"]) for e in freq]
    ax.bar(xs - 0.2, g_atm, 0.38, color=plots.MUTED, label="before costs")
    ax.bar(xs + 0.2, n_atm, 0.38, color=plots.SERIES[0], label="after costs")
    for i in range(len(freq)):
        ax.text(i - 0.2, max(g_atm[i], 0) + 0.003, f"{g_atm[i]:.3f}%", ha="center", fontsize=9,
                color=plots.TEXT_2)
        ax.text(i + 0.2, max(n_atm[i], 0) + 0.003, f"{n_atm[i]:.3f}%", ha="center", fontsize=9)
    ax.axhline(0, color=plots.MUTED, lw=0.8)
    ax.set_xticks(xs, list(freq.values()))
    ax.set_ylabel("hedged seller, average per month, % of NIFTY")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    ax.set_title("Hedging less often cut costs, but earned less before costs too")
    plots.save(fig, out_dir, "costs_frequency")

    out = {"book": f"{BOOK_LOTS} lots of {RATES['lot']}"}
    for leg, (name, *_r) in LEGS.items():
        rows = {}
        for hs in HALF_SPREADS:
            c = with_costs(hedge_table(iv, s, 1), hs).query("leg == @leg")
            rows[f"half-spread {hs:g} pt"] = {
                "seller unhedged net": round(pct(c["seller_net"]), 3),
                "buyer net": round(pct(c["buyer_net"]), 3),
                "hedged daily net": round(pct(c["hedged_net"]), 3)}
        g = daily[daily["leg"] == leg]
        old = with_costs(hedge_table(iv, s, 1), 1.0, RATES_PRE_2026).query("leg == @leg")
        out[name] = {
            "gross hedged / unhedged": (round(pct(g["hedged"]), 3), round(pct(g["unhedged"]), 3)),
            "hedge turnover x notional": round(float(((g["bought"] + g["sold"]) / g["spot"])
                                                     .mean()), 2),
            "option cost / hedge cost (1-pt spread)": (round(pct(g["sell_cost"]), 4),
                                                        round(pct(g["hedge_cost"]), 4)),
            "STT share of hedge cost": round(float(g["hedge_stt"].sum() / g["hedge_cost"].sum()),
                                             3),
            "hedge cost at pre-2026 STT": round(pct(old["hedge_cost"]), 4),
            **rows,
            "weekly hedged gross / net": (
                round(pct(tables[5].query("leg == @leg")["hedged"]), 3),
                round(pct(tables[5].query("leg == @leg")["hedged_net"]), 3)),
        }
    return out


MERTON = Path("docs/data/nifty_merton.csv")  # fitted parameters only, committed for the site
DROPS = (0.03, 0.04, 0.05)


def jump_drop_rate(lam, mu_j, delta, drop: float) -> float:
    """Jumps a year that take NIFTY down by more than `drop`, under fitted Merton parameters
    (ignoring the small diffusion part of a single day)."""
    return float(lam * norm.cdf((np.log(1 - drop) - mu_j) / delta))


def report_merton(out_dir: Path) -> dict:
    """Merton jump-diffusion fitted to each month's NIFTY smile: fit, implied crashes, stability."""
    from bsp.iv import implied_vol
    from bsp.merton import fit_smile, merton_price

    summary, grid = iv_tables(pd.read_parquet(OPTIONS), nifty_and_vix()["S"])
    rows = []
    for day, row in grid.iterrows():
        ok = row.notna()
        if ok.sum() < 8:
            continue
        m, iv = row.index[ok].to_numpy(), row[ok].to_numpy()
        fit = fit_smile(m, iv, summary.loc[day, "days"] / 365, RF)
        fit["rmse_bs"] = float(np.sqrt(np.mean((iv - np.interp(1.0, m, iv)) ** 2)))
        rows.append({"date": day, **fit})
    fits = pd.DataFrame(rows).set_index("date")
    fits.to_csv(MERTON, float_format="%.5f")

    med = grid.median()
    t_med = summary["days"].median() / 365
    mfit = fit_smile(med.index.to_numpy(), med.to_numpy(), t_med, RF)
    x = np.linspace(GRID.min(), GRID.max(), 60)
    curve = [implied_vol(merton_price(1.0, k, t_med, RF, mfit["sigma"], "put" if k < 1 else "call",
                                      RF, mfit["lam"], mfit["mu_j"], mfit["delta"]),
                         1.0, k, t_med, RF, "put" if k < 1 else "call", RF) for k in x]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(med.index * 100, med * 100, "o", color=plots.SERIES[0], ms=5,
            label="NIFTY options, median month")
    ax.plot(x * 100, np.array(curve) * 100, color=plots.SERIES[1],
            label="Merton jump-diffusion fit")
    ax.axhline(float(med.loc[1.0]) * 100, color=plots.MUTED, ls="--", lw=1,
               label="Black-Scholes: one volatility")
    ax.set_xlabel("strike, % of the forward price")
    ax.set_ylabel("implied volatility, %")
    ax.legend(loc="upper center")
    ax.set_title("Adding crash jumps lets the model fit the smile Black-Scholes can't")
    plots.save(fig, out_dir, "merton_smile")

    s = nifty_and_vix()["S"]
    r = np.log(s).diff()
    r = r[(r.index >= summary.index.min()) & (r.index <= summary["expiry"].max())].dropna()
    years = len(r) / 252
    actual = {d: float((r < np.log(1 - d)).sum() / years) for d in DROPS}
    rates = {d: [jump_drop_rate(f.lam, f.mu_j, f.delta, d) for f in fits.itertuples()]
             for d in DROPS}
    implied = {d: float(np.median(rates[d])) for d in DROPS}  # robust to months at the λ bound
    fig, ax = plt.subplots(figsize=(9, 4.6))
    xs = np.arange(len(DROPS))
    ax.bar(xs - 0.2, [implied[d] for d in DROPS], 0.38, color=plots.SERIES[1],
           label="priced into options (Merton fit, median month)")
    ax.bar(xs + 0.2, [actual[d] for d in DROPS], 0.38, color=plots.SERIES[0],
           label="NIFTY actually, 2015–2026")
    for i, d in enumerate(DROPS):
        ax.text(i - 0.2, implied[d], f"{implied[d]:.2f}", ha="center", va="bottom", fontsize=9)
        ax.text(i + 0.2, actual[d], f"{actual[d]:.2f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(xs, [f"daily drop worse than −{d:.0%}" for d in DROPS])
    ax.set_ylabel("per year")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    ax.set_title("Options priced in more of the biggest down-days than NIFTY delivered")
    plots.save(fig, out_dir, "merton_crashes")

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5.4), sharex=True)
    a1.plot(fits.index, fits["lam"], color=plots.SERIES[0], marker="o", ms=3)
    a1.set_ylabel("jumps a year (λ)")
    a2.plot(fits.index, fits["mu_j"] * 100, color=plots.SERIES[1], marker="o", ms=3)
    a2.set_ylabel("average jump, %")
    fig.suptitle("Refitted each month, the crash parameters swing widely", x=0.06, ha="left",
                 fontsize=13, fontweight="semibold", color=plots.TEXT)
    plots.save(fig, out_dir, "merton_params")

    q = lambda c: [round(float(v), 3) for v in fits[c].quantile([0.25, 0.5, 0.75])]  # noqa: E731
    return {
        "months": len(fits),
        "median-smile fit (sigma, lam, mu_j, delta)":
            tuple(round(float(mfit[k]), 3) for k in ("sigma", "lam", "mu_j", "delta")),
        "median-smile rmse pts (Merton / BS)": (round(mfit["rmse"] * 100, 2),
                                                round(float(np.sqrt(np.mean(
                                                    (med - med.loc[1.0]) ** 2))) * 100, 2)),
        "monthly rmse median pts (Merton / BS)": (round(float(fits["rmse"].median()) * 100, 2),
                                                  round(float(fits["rmse_bs"].median()) * 100, 2)),
        "lam quartiles": q("lam"), "mu_j quartiles": q("mu_j"), "delta quartiles": q("delta"),
        "sigma quartiles": q("sigma"),
        "lam at upper bound (20) months": int((fits["lam"] > 19.9).sum()),
        "drops per year implied / actual":
            {f"-{d:.0%}": (round(implied[d], 2), round(actual[d], 2)) for d in DROPS},
        "drops per year implied, mean of months": {f"-{d:.0%}": round(float(np.mean(rates[d])), 2)
                                                   for d in DROPS},
        "lam max month": f"{fits['lam'].idxmax():%Y-%m-%d} {fits['lam'].max():.1f}",
    }


REPORTS = {"pricing": report_pricing, "greeks": report_greeks, "iv": report_iv,
           "hedging": report_hedging, "black76": report_black76, "costs": report_costs,
           "merton": report_merton}
